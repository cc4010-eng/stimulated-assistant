# Stimulated Assistant

AI-assisted interviewing and coding for stimulated recall research.

In a stimulated recall interview, a participant reviews a record of their own
activity (a classroom video, a screen recording, samples of student work),
stops at key moments, and says what they were thinking at the time. This
project supports the three stages of that kind of study: selecting moments in
the material, running the interview, and coding the answers.

## Status

Early build. What works today:

- Create and list studies, add participants
- Upload an audio or video recording to a study
- Transcript view with timestamps and speakers; click a line to jump to it
- Moment selection: the system suggests moments to discuss, the researcher
  accepts, edits or removes them and adds their own. Every decision is logged.
- Text interview over the confirmed moments, with three control modes: the AI
  leads, the AI asks for approval first, or the researcher leads and the AI
  only suggests. The mode can change mid-interview.
- Interview rules enforced in code: follow-up limit, time budget split across
  the remaining moments, no leading wording, no repeated question
- Coding: a codebook per study, suggested codes on each answer, review by the
  researcher, and a CSV export of accepted codings. Low-confidence suggestions
  wait for review; nothing the researcher decided is overwritten on a re-run.
- Postgres schema managed with Alembic
- Structured JSON request logs with a request id
- CI: lint and tests for the backend, lint and build for the frontend

Transcription currently uses a stub that returns the same short exchange for
every file. It exists so the upload-to-transcript path can run without a
speech API key; a real provider plugs in behind the same interface
(`backend/app/transcription.py`).

Moment suggestions come from a rule-based baseline that flags long pauses
between speakers (`backend/app/suggestion.py`). A model-based suggester will
sit behind the same interface and be measured against it.

Follow-up questions come from a keyword stand-in
(`backend/app/interview/policy.py`). The rules in
`backend/app/interview/harness.py` apply to whatever the policy proposes, so
they will apply unchanged to a model.

Code suggestions come from keyword overlap with each code's name and
definition (`backend/app/coding.py`). It misses paraphrases and is fooled by
negation; it is the floor a model-based coder will be compared against.

Not built yet: real transcription, model-based suggestions, follow-ups and
coding, and voice.

## Run it locally

Requirements: Docker, Node 22.

```bash
make up     # Postgres and the API on http://localhost:8000
make web    # web app on http://localhost:3000
```

API docs are at http://localhost:8000/docs.

## Develop

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Tests run against in-memory SQLite and a temporary upload folder, so they do
not need Docker.

To change the schema, edit `backend/app/models.py`, then:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, tests
frontend/   Next.js app
```

## License

MIT
