import pytest

from app.interview import harness
from app.interview.policy import KeywordFollowUpPolicy


@pytest.mark.parametrize(
    "question",
    [
        "Don't you think the student was confused?",
        "Was that because you were running out of time?",
        "You must have felt frustrated.",
        "So you ignored him, right?",
        "Surely you saw his hand up.",
    ],
)
def test_leading_questions_are_caught(question):
    assert harness.find_leading_phrase(question) is not None


@pytest.mark.parametrize(
    "question",
    [
        "What did you notice at that moment?",
        "What led you to that?",
        "Can you say more about that?",
        "What is the right way to read this, in your view?",
    ],
)
def test_open_questions_pass(question):
    assert harness.find_leading_phrase(question) is None


def test_moment_allowance_splits_remaining_time():
    assert harness.moment_allowance(600, 4) == 150
    assert harness.moment_allowance(100, 3) == 33
    assert harness.moment_allowance(100, 0) == 0


def test_policy_follows_up_on_short_answers():
    proposal = KeywordFollowUpPolicy().propose("Not much, honestly.", "What did you notice?")
    assert proposal.question is not None
    assert "short answer" in proposal.reason


def test_policy_follows_up_on_cue_words():
    answer = "I let it go for now since I was worried he would stop talking if I corrected him."
    proposal = KeywordFollowUpPolicy().propose(answer, "What did you notice?")
    assert proposal.question == "What were you concerned might happen?"
    assert '"worried"' in proposal.reason


def test_policy_moves_on_when_nothing_stands_out():
    answer = "It was a routine part of the lesson and I just moved to the next example as planned."
    assert KeywordFollowUpPolicy().propose(answer, "What did you notice?").question is None
