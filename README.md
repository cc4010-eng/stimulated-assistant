# Stimulated Assistant

AI-assisted interviewing and coding for stimulated recall research.

In a stimulated recall interview, a participant reviews a record of their own
activity (a classroom video, a screen recording, samples of student work),
stops at key moments, and says what they were thinking at the time. This
project supports the three stages of that kind of study: selecting moments in
the material, running the interview, and coding the answers.

## Status

Early scaffold. What works today:

- Create and list studies, add participants (API and a minimal web page)
- Postgres schema managed with Alembic
- Structured JSON request logs with a request id
- CI: lint and tests for the backend, lint and build for the frontend

Not built yet: material upload and transcription, moment selection, the
interview loop, voice, coding and review.

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

Tests run against in-memory SQLite, so they do not need Docker.

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
