import pytest

from app.main import app
from app.models import TranscriptSegment
from app.storage import LocalStorage, get_storage
from app.suggestion import PauseSuggester


@pytest.fixture
def material_id(client, tmp_path):
    app.dependency_overrides[get_storage] = lambda: LocalStorage(str(tmp_path))
    study_id = client.post("/studies", json={"title": "Pilot"}).json()["id"]
    response = client.post(
        f"/studies/{study_id}/materials", files={"file": ("lesson.m4a", b"audio", "audio/mp4")}
    )
    return response.json()["id"]


def segment(speaker, start_ms, end_ms):
    return TranscriptSegment(speaker=speaker, start_ms=start_ms, end_ms=end_ms, text="...")


def test_pause_suggester_flags_long_gaps_between_speakers():
    segments = [
        segment("Teacher", 0, 4000),
        segment("Student", 4300, 9000),  # 0.3 s gap: too short
        segment("Teacher", 11500, 14000),  # 2.5 s gap: flagged
        segment("Teacher", 17000, 19000),  # same speaker: not a response
    ]

    suggestions = PauseSuggester(min_gap_ms=1500).suggest(segments)

    assert [s.timestamp_ms for s in suggestions] == [9000]
    assert "2.5 s" in suggestions[0].reason


def test_suggest_creates_candidates(client, material_id):
    moments = client.post(f"/materials/{material_id}/moments/suggest").json()

    assert len(moments) == 1
    assert moments[0]["source"] == "ai"
    assert moments[0]["status"] == "candidate"
    assert moments[0]["timestamp_ms"] == 9100


def test_suggesting_twice_does_not_duplicate(client, material_id):
    client.post(f"/materials/{material_id}/moments/suggest")
    moments = client.post(f"/materials/{material_id}/moments/suggest").json()
    assert len(moments) == 1


def test_removed_suggestion_does_not_come_back(client, material_id):
    moment = client.post(f"/materials/{material_id}/moments/suggest").json()[0]
    client.patch(f"/moments/{moment['id']}", json={"status": "removed"})

    assert client.post(f"/materials/{material_id}/moments/suggest").json() == []
    assert client.get(f"/materials/{material_id}/moments").json() == []


def test_accept_and_edit(client, material_id):
    moment = client.post(f"/materials/{material_id}/moments/suggest").json()[0]

    updated = client.patch(
        f"/moments/{moment['id']}",
        json={"status": "confirmed", "question": "What did you notice when he said that?"},
    ).json()

    assert updated["status"] == "confirmed"
    assert updated["question"] == "What did you notice when he said that?"


def test_researcher_can_add_a_moment(client, material_id):
    response = client.post(
        f"/materials/{material_id}/moments",
        json={"timestamp_ms": 2000, "question": "Why did you start with this example?"},
    )

    assert response.status_code == 201
    assert response.json()["source"] == "researcher"
    assert response.json()["status"] == "confirmed"

    client.post(f"/materials/{material_id}/moments/suggest")
    listed = client.get(f"/materials/{material_id}/moments").json()
    assert [m["timestamp_ms"] for m in listed] == [2000, 9100]


def test_every_decision_is_logged(client, material_id):
    moment = client.post(f"/materials/{material_id}/moments/suggest").json()[0]
    client.patch(f"/moments/{moment['id']}", json={"question": "What made you pause?"})
    client.patch(f"/moments/{moment['id']}", json={"status": "confirmed"})
    client.patch(f"/moments/{moment['id']}", json={"status": "removed"})

    events = client.get(f"/materials/{material_id}/moments/events").json()

    assert [(e["action"], e["actor"]) for e in events] == [
        ("suggested", "ai"),
        ("edited", "researcher"),
        ("accepted", "researcher"),
        ("removed", "researcher"),
    ]
    assert events[0]["detail"] == {"suggester": "PauseSuggester"}
    assert events[1]["detail"]["after"] == "What made you pause?"


def test_unchanged_update_logs_nothing(client, material_id):
    moment = client.post(f"/materials/{material_id}/moments/suggest").json()[0]
    client.patch(f"/moments/{moment['id']}", json={"question": moment["question"]})

    events = client.get(f"/materials/{material_id}/moments/events").json()
    assert [e["action"] for e in events] == ["suggested"]


def test_removed_moment_cannot_be_changed(client, material_id):
    moment = client.post(f"/materials/{material_id}/moments/suggest").json()[0]
    client.patch(f"/moments/{moment['id']}", json={"status": "removed"})

    response = client.patch(f"/moments/{moment['id']}", json={"status": "confirmed"})
    assert response.status_code == 409


def test_validation_and_not_found(client, material_id):
    url = f"/materials/{material_id}/moments"
    assert client.post(url, json={"timestamp_ms": -1, "question": "Q"}).status_code == 422
    assert client.post(url, json={"timestamp_ms": 0, "question": ""}).status_code == 422
    assert client.patch("/moments/nope", json={"status": "confirmed"}).status_code == 404
    assert client.post("/materials/nope/moments/suggest").status_code == 404
