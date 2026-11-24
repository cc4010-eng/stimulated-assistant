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

Not built yet: real transcription, model-based suggestions, the interview
loop, voice, coding and review.

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
