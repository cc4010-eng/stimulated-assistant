import csv
import io

import pytest

from app.coding import CodeProposal, KeywordCoder, get_coder
from app.main import app
from app.models import Code
from app.storage import LocalStorage, get_storage

ANSWERS = [
    "I was worried he would stop participating if I corrected the misconception right away.",
    "It was a routine part of the lesson and I just moved to the next example as planned.",
]


@pytest.fixture
def study_id(client, tmp_path):
    app.dependency_overrides[get_storage] = lambda: LocalStorage(str(tmp_path))
    return client.post("/studies", json={"title": "Pilot"}).json()["id"]


@pytest.fixture
def codes(client, study_id):
    url = f"/studies/{study_id}/codes"
    participation = client.post(
        url,
        json={
            "name": "Attends to participation",
            "description": "Worried about who is participating or staying silent",
        },
    ).json()
    misconception = client.post(
        url,
        json={
            "name": "Notices misconception",
            "description": "Identifies an error in reasoning",
        },
    ).json()
    return {"participation": participation, "misconception": misconception}


@pytest.fixture
def interview_id(client, study_id):
    material = client.post(
        f"/studies/{study_id}/materials", files={"file": ("a.m4a", b"audio", "audio/mp4")}
    ).json()
    for timestamp_ms in (2000, 9100):
        client.post(
            f"/materials/{material['id']}/moments",
            json={"timestamp_ms": timestamp_ms, "question": f"What happened at {timestamp_ms}?"},
        )
    interview = client.post(
        f"/materials/{material['id']}/interviews", json={"max_followups": 0}
    ).json()
    for answer in ANSWERS:
        interview = client.post(
            f"/interviews/{interview['id']}/answer", json={"text": answer}
        ).json()
    assert interview["state"] == "finished"
    return interview["id"]


def codings_by_turn(summary):
    return {turn["text"]: {c["code_name"]: c for c in turn["codings"]} for turn in summary["turns"]}


def test_keyword_coder_scores_by_distinct_matches():
    codebook = [
        Code(id="a", name="Attends to participation", description="Worried about silence"),
        Code(id="b", name="Time pressure", description="Running out of minutes"),
    ]

    proposals = KeywordCoder().code("I was worried about participation today.", codebook)

    assert [p.code_id for p in proposals] == ["a"]
    assert proposals[0].confidence == 0.67
    assert proposals[0].rationale == "Matched: parti, worri"


def test_codebook_rejects_duplicate_names(client, study_id, codes):
    response = client.post(f"/studies/{study_id}/codes", json={"name": "notices misconception"})
    assert response.status_code == 409
    assert len(client.get(f"/studies/{study_id}/codes").json()) == 2


def test_confident_codings_are_accepted_and_weak_ones_wait_for_review(client, interview_id, codes):
    summary = client.post(f"/interviews/{interview_id}/code").json()

    first = codings_by_turn(summary)[ANSWERS[0]]
    assert first["Attends to participation"]["status"] == "accepted"
    assert first["Attends to participation"]["confidence"] == 0.67
    assert first["Notices misconception"]["status"] == "needs_review"
    assert first["Notices misconception"]["confidence"] == 0.33
    assert codings_by_turn(summary)[ANSWERS[1]] == {}
    assert summary["needs_review"] == 1


def test_only_participant_answers_are_coded(client, interview_id, codes):
    summary = client.post(f"/interviews/{interview_id}/code").json()
    assert [turn["text"] for turn in summary["turns"]] == ANSWERS


def test_researcher_review_is_kept_when_coding_runs_again(client, interview_id, codes):
    summary = client.post(f"/interviews/{interview_id}/code").json()
    weak = codings_by_turn(summary)[ANSWERS[0]]["Notices misconception"]

    rejected = client.patch(f"/codings/{weak['id']}", json={"status": "rejected"}).json()
    assert rejected["status"] == "rejected"

    again = client.post(f"/interviews/{interview_id}/code").json()
    assert codings_by_turn(again)[ANSWERS[0]]["Notices misconception"]["status"] == "rejected"
    assert again["needs_review"] == 0


def test_researcher_can_add_a_code_the_coder_missed(client, interview_id, codes):
    client.post(f"/interviews/{interview_id}/code")
    turn = client.get(f"/interviews/{interview_id}/codings").json()["turns"][1]

    added = client.post(
        f"/interviews/{interview_id}/codings",
        json={"turn_position": turn["position"], "code_id": codes["misconception"]["id"]},
    )

    assert added.status_code == 201
    assert added.json()["source"] == "researcher"
    assert added.json()["status"] == "accepted"


def test_adding_a_code_the_ai_was_unsure_about_accepts_it(client, interview_id, codes):
    summary = client.post(f"/interviews/{interview_id}/code").json()
    turn = summary["turns"][0]

    added = client.post(
        f"/interviews/{interview_id}/codings",
        json={"turn_position": turn["position"], "code_id": codes["misconception"]["id"]},
    ).json()

    assert added["status"] == "accepted"
    assert added["source"] == "ai"
    after = client.get(f"/interviews/{interview_id}/codings").json()
    assert len(after["turns"][0]["codings"]) == 2


def test_cannot_code_an_ai_question(client, interview_id, codes):
    response = client.post(
        f"/interviews/{interview_id}/codings",
        json={"turn_position": 0, "code_id": codes["misconception"]["id"]},
    )
    assert response.status_code == 422


def test_export_contains_only_accepted_codings(client, interview_id, codes):
    client.post(f"/interviews/{interview_id}/code")

    response = client.get(f"/interviews/{interview_id}/codings.csv")

    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [(row["code"], row["moment_ms"], row["source"]) for row in rows] == [
        ("Attends to participation", "2000", "ai")
    ]
    assert rows[0]["answer"] == ANSWERS[0]


def test_coder_is_swappable(client, interview_id, codes):
    class AlwaysSure:
        def code(self, answer, codebook):
            return [CodeProposal(codebook[0].id, 0.95, "stub")]

    app.dependency_overrides[get_coder] = lambda: AlwaysSure()
    summary = client.post(f"/interviews/{interview_id}/code").json()

    assert all(len(turn["codings"]) == 1 for turn in summary["turns"])
    assert summary["needs_review"] == 0


def test_coding_requires_a_finished_interview_and_a_codebook(client, study_id, interview_id):
    assert client.post(f"/interviews/{interview_id}/code").status_code == 409  # no codebook

    material = client.post(
        f"/studies/{study_id}/materials", files={"file": ("b.m4a", b"audio", "audio/mp4")}
    ).json()
    client.post(
        f"/materials/{material['id']}/moments", json={"timestamp_ms": 0, "question": "Why?"}
    )
    running = client.post(f"/materials/{material['id']}/interviews", json={}).json()
    client.post(f"/studies/{study_id}/codes", json={"name": "Anything"})
    assert client.post(f"/interviews/{running['id']}/code").status_code == 409  # not finished


def test_not_found(client):
    assert client.get("/studies/nope/codes").status_code == 404
    assert client.post("/interviews/nope/code").status_code == 404
    assert client.patch("/codings/nope", json={"status": "accepted"}).status_code == 404
