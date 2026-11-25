from datetime import UTC, datetime, timedelta

import pytest

from app.clock import get_clock
from app.interview.policy import FollowUpProposal, get_followup_policy
from app.main import app
from app.storage import LocalStorage, get_storage

LONG = "It was a routine part of the lesson and I just moved to the next example as planned."
WORRIED = "I let it go for now since I was worried he would stop talking if I corrected him."


class FakeClock:
    def __init__(self):
        self.current = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)

    def now(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class ScriptedPolicy:
    """Proposes the given follow-ups in order, then nothing."""

    def __init__(self, *questions):
        self.questions = list(questions)

    def propose(self, answer, moment_question):
        if self.questions:
            return FollowUpProposal(self.questions.pop(0), "scripted")
        return FollowUpProposal(None, "script finished")


@pytest.fixture
def clock():
    fake = FakeClock()
    app.dependency_overrides[get_clock] = lambda: fake
    return fake


@pytest.fixture
def material_id(client, tmp_path):
    app.dependency_overrides[get_storage] = lambda: LocalStorage(str(tmp_path))
    study_id = client.post("/studies", json={"title": "Pilot"}).json()["id"]
    material = client.post(
        f"/studies/{study_id}/materials", files={"file": ("lesson.m4a", b"audio", "audio/mp4")}
    ).json()
    for timestamp_ms, question in [
        (2000, "Why did you open with this comparison?"),
        (9100, "You paused here. What did you notice?"),
        (14000, "What made you call on Lin?"),
    ]:
        client.post(
            f"/materials/{material['id']}/moments",
            json={"timestamp_ms": timestamp_ms, "question": question},
        )
    return material["id"]


def use_policy(policy):
    app.dependency_overrides[get_followup_policy] = lambda: policy


def start(client, material_id, **options):
    response = client.post(f"/materials/{material_id}/interviews", json=options)
    assert response.status_code == 201, response.text
    return response.json()


def act(client, interview, action, **body):
    response = client.post(f"/interviews/{interview['id']}/{action}", json=body or None)
    assert response.status_code == 200, response.text
    return response.json()


def events(client, interview):
    return client.get(f"/interviews/{interview['id']}/events").json()


def spoken(interview):
    return [(turn["speaker"], turn["text"]) for turn in interview["turns"]]


def test_ai_leads_runs_through_every_moment(client, material_id, clock):
    interview = start(client, material_id, mode="ai_leads")

    assert interview["state"] == "awaiting_answer"
    assert interview["moments_total"] == 3
    assert spoken(interview) == [("ai", "Why did you open with this comparison?")]

    for _ in range(3):
        clock.advance(60)
        interview = act(client, interview, "answer", text=LONG)

    assert interview["state"] == "finished"
    assert interview["finished_reason"] == "completed"
    assert [speaker for speaker, _ in spoken(interview)] == ["ai", "participant"] * 3


def test_follow_up_is_asked_on_a_cue_and_the_reason_is_logged(client, material_id, clock):
    interview = start(client, material_id, mode="ai_leads")
    clock.advance(30)

    interview = act(client, interview, "answer", text=WORRIED)

    assert spoken(interview)[-1] == ("ai", "What were you concerned might happen?")
    assert interview["followups_used"] == 1
    assert interview["moment_index"] == 0
    assert interview["last_decision"]["decision"] == "follow_up"
    assert interview["last_decision"]["policy_reason"] == 'cue word "worried"'


def test_follow_ups_stop_at_the_limit(client, material_id, clock):
    use_policy(ScriptedPolicy("First?", "Second?", "Third?"))
    interview = start(client, material_id, mode="ai_leads", max_followups=2)

    for _ in range(3):
        clock.advance(10)
        interview = act(client, interview, "answer", text=LONG)

    assert interview["moment_index"] == 1
    assert interview["last_decision"]["reason"] == "followup_limit_reached"
    assert "Third?" not in [text for _, text in spoken(interview)]


def test_moment_time_allowance_cuts_follow_ups_short(client, material_id, clock):
    use_policy(ScriptedPolicy("First?"))
    interview = start(client, material_id, mode="ai_leads", budget_minutes=3)
    assert interview["moment_allowance_seconds"] == 60

    clock.advance(75)
    interview = act(client, interview, "answer", text=LONG)

    assert interview["last_decision"]["reason"] == "moment_time_used"
    assert interview["moment_index"] == 1
    # The time lost on the first moment is taken out of the ones that remain.
    assert interview["moment_allowance_seconds"] == 52


def test_interview_ends_when_the_budget_runs_out(client, material_id, clock):
    interview = start(client, material_id, mode="ai_leads", budget_minutes=1)

    clock.advance(61)
    interview = act(client, interview, "answer", text=LONG)

    assert interview["state"] == "finished"
    assert interview["finished_reason"] == "time_up"
    finished = events(client, interview)[-1]
    assert finished["type"] == "finished"
    assert finished["detail"]["moments_covered"] == 1
    assert len(finished["detail"]["moments_skipped"]) == 2


def test_leading_follow_up_is_replaced_and_logged(client, material_id, clock):
    use_policy(ScriptedPolicy("Don't you think he was confused?"))
    interview = start(client, material_id, mode="ai_leads")

    interview = act(client, interview, "answer", text=LONG)

    assert spoken(interview)[-1] == (
        "ai",
        "Can you say more about what you were thinking at that point?",
    )
    decision = interview["last_decision"]
    assert decision["blocked_question"] == "Don't you think he was confused?"
    assert decision["leading_phrase"].lower() == "don't you think"


def test_the_same_question_is_not_asked_twice(client, material_id, clock):
    use_policy(ScriptedPolicy("What led you to that?", "What led you to that?"))
    interview = start(client, material_id, mode="ai_leads")

    interview = act(client, interview, "answer", text=LONG)
    interview = act(client, interview, "answer", text=LONG)

    assert interview["last_decision"]["reason"] == "would_repeat_question"
    assert [text for _, text in spoken(interview)].count("What led you to that?") == 1


def test_ai_asks_first_waits_for_approval(client, material_id, clock):
    interview = start(client, material_id, mode="ai_asks_first")

    assert interview["state"] == "awaiting_approval"
    assert interview["pending_question"] == "Why did you open with this comparison?"
    assert spoken(interview) == []

    interview = act(client, interview, "approve")
    assert interview["state"] == "awaiting_answer"
    assert spoken(interview) == [("ai", "Why did you open with this comparison?")]


def test_researcher_can_edit_a_question_before_approving(client, material_id, clock):
    interview = start(client, material_id, mode="ai_asks_first")

    interview = act(client, interview, "approve", text="Why start with thirds and fifths?")

    assert spoken(interview) == [("ai", "Why start with thirds and fifths?")]
    approved = [e for e in events(client, interview) if e["type"] == "question_approved"][0]
    assert approved["detail"]["edited"] is True
    assert approved["detail"]["before"] == "Why did you open with this comparison?"


def test_skipping_moves_to_the_next_moment(client, material_id, clock):
    interview = start(client, material_id, mode="ai_asks_first")

    interview = act(client, interview, "skip")

    assert interview["moment_index"] == 1
    assert interview["pending_question"] == "You paused here. What did you notice?"
    assert spoken(interview) == []


def test_ai_stays_silent_when_approval_times_out(client, material_id, clock):
    interview = start(client, material_id, mode="ai_asks_first")
    interview = act(client, interview, "approve")
    interview = act(client, interview, "answer", text=WORRIED)
    assert interview["pending_question"] == "What were you concerned might happen?"

    interview = act(client, interview, "expire")

    assert interview["state"] == "researcher_turn"
    assert interview["pending_question"] is None
    assert spoken(interview)[-1][0] == "participant"

    interview = act(client, interview, "say", text="What happened next?")
    assert spoken(interview)[-1] == ("researcher", "What happened next?")
    assert interview["state"] == "awaiting_answer"


def test_researcher_leads_and_the_ai_only_suggests(client, material_id, clock):
    interview = start(client, material_id, mode="researcher_leads")

    assert interview["state"] == "researcher_turn"
    assert interview["suggested_question"] == "Why did you open with this comparison?"

    interview = act(client, interview, "say", text="Tell me about how you started.")
    interview = act(client, interview, "answer", text=WORRIED)

    assert interview["state"] == "researcher_turn"
    assert interview["suggested_question"] == "What were you concerned might happen?"
    assert "ai" not in [speaker for speaker, _ in spoken(interview)]

    interview = act(client, interview, "next")
    assert interview["moment_index"] == 1


def test_researcher_leads_is_never_cut_off_by_the_clock(client, material_id, clock):
    interview = start(client, material_id, mode="researcher_leads", budget_minutes=1)
    interview = act(client, interview, "say", text="Tell me about how you started.")

    clock.advance(600)
    interview = act(client, interview, "answer", text=LONG)

    assert interview["state"] == "researcher_turn"
    assert interview["last_decision"]["reason"] == "time_up"
    assert interview["remaining_seconds"] == 0


def test_switching_mode_hands_over_the_held_question(client, material_id, clock):
    interview = start(client, material_id, mode="ai_asks_first")
    assert interview["state"] == "awaiting_approval"

    interview = act(client, interview, "mode", mode="ai_leads")
    assert spoken(interview) == [("ai", "Why did you open with this comparison?")]

    interview = act(client, interview, "answer", text=WORRIED)
    interview = act(client, interview, "mode", mode="researcher_leads")
    assert interview["mode"] == "researcher_leads"
    assert interview["state"] == "awaiting_answer"


def test_event_log_tells_the_whole_story(client, material_id, clock):
    interview = start(client, material_id, mode="ai_asks_first", budget_minutes=30)
    interview = act(client, interview, "approve")
    clock.advance(40)
    interview = act(client, interview, "answer", text=LONG)
    interview = act(client, interview, "end")

    log = events(client, interview)
    assert [e["position"] for e in log] == list(range(len(log)))
    assert [e["type"] for e in log] == [
        "started",
        "moment_opened",
        "question_proposed",
        "question_approved",
        "question_asked",
        "answer_received",
        "followup_decided",
        "moment_closed",
        "moment_opened",
        "question_proposed",
        "moment_closed",
        "finished",
    ]
    assert log[7]["detail"] == {
        "moment_id": log[1]["detail"]["moment_id"],
        "reason": "nothing_to_follow_up",
        "seconds": 40,
        "followups_used": 0,
    }


def test_actions_out_of_turn_are_rejected(client, material_id, clock):
    interview = start(client, material_id, mode="ai_leads")
    url = f"/interviews/{interview['id']}"

    assert client.post(f"{url}/approve", json={}).status_code == 409
    assert client.post(f"{url}/expire").status_code == 409
    assert client.post(f"{url}/say", json={"text": "Hello"}).status_code == 409

    client.post(f"{url}/end")
    assert client.post(f"{url}/answer", json={"text": "Too late"}).status_code == 409
    assert client.post(f"{url}/mode", json={"mode": "ai_leads"}).status_code == 409


def test_cannot_start_without_confirmed_moments(client, tmp_path, clock):
    app.dependency_overrides[get_storage] = lambda: LocalStorage(str(tmp_path))
    study_id = client.post("/studies", json={"title": "Pilot"}).json()["id"]
    material = client.post(
        f"/studies/{study_id}/materials", files={"file": ("a.m4a", b"audio", "audio/mp4")}
    ).json()
    client.post(f"/materials/{material['id']}/moments/suggest")  # candidates only

    response = client.post(f"/materials/{material['id']}/interviews", json={})
    assert response.status_code == 409


def test_validation_and_not_found(client, material_id, clock):
    assert client.post("/materials/nope/interviews", json={}).status_code == 404
    assert client.get("/interviews/nope").status_code == 404
    url = f"/materials/{material_id}/interviews"
    assert client.post(url, json={"mode": "autopilot"}).status_code == 422
    assert client.post(url, json={"budget_minutes": 0}).status_code == 422
