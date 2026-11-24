from pathlib import Path

import pytest

from app.config import settings
from app.db import get_db
from app.main import app
from app.pipeline import process_material
from app.storage import LocalStorage, get_storage
from app.transcription import Segment, get_transcriber


@pytest.fixture
def storage_dir(tmp_path):
    app.dependency_overrides[get_storage] = lambda: LocalStorage(str(tmp_path))
    return tmp_path


@pytest.fixture
def study_id(client):
    return client.post("/studies", json={"title": "Pilot"}).json()["id"]


def upload(client, study_id, name="lesson3.m4a", content=b"fake audio", mime="audio/mp4"):
    return client.post(f"/studies/{study_id}/materials", files={"file": (name, content, mime)})


def test_upload_stores_file_and_transcribes(client, study_id, storage_dir):
    response = upload(client, study_id)

    assert response.status_code == 201
    material = response.json()
    assert material["status"] == "ready"
    assert material["filename"] == "lesson3.m4a"
    assert material["size_bytes"] == len(b"fake audio")

    segments = material["segments"]
    assert [s["position"] for s in segments] == [0, 1, 2]
    assert segments[1]["speaker"] == "Student"
    assert all(s["start_ms"] < s["end_ms"] for s in segments)

    stored = list(Path(storage_dir).rglob("*.m4a"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"fake audio"


def test_list_and_get_material(client, study_id, storage_dir):
    material_id = upload(client, study_id).json()["id"]

    listed = client.get(f"/studies/{study_id}/materials").json()
    assert [m["id"] for m in listed] == [material_id]
    assert "segments" not in listed[0]

    fetched = client.get(f"/materials/{material_id}").json()
    assert len(fetched["segments"]) == 3


def test_file_can_be_played_back(client, study_id, storage_dir):
    material_id = upload(client, study_id).json()["id"]

    response = client.get(f"/materials/{material_id}/file")
    assert response.status_code == 200
    assert response.content == b"fake audio"
    assert response.headers["content-type"] == "audio/mp4"

    partial = client.get(f"/materials/{material_id}/file", headers={"Range": "bytes=0-3"})
    assert partial.status_code == 206
    assert partial.content == b"fake"


def test_rejects_non_media_file(client, study_id, storage_dir):
    response = upload(client, study_id, name="notes.txt", mime="text/plain")
    assert response.status_code == 415
    assert list(Path(storage_dir).rglob("*")) == []


def test_rejects_file_over_limit(client, study_id, storage_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    response = upload(client, study_id, content=b"x" * (1024 * 1024 + 1))
    assert response.status_code == 413
    assert [p for p in Path(storage_dir).rglob("*") if p.is_file()] == []


def test_client_filename_cannot_escape_storage(client, study_id, storage_dir):
    response = upload(client, study_id, name="../../etc/passwd.m4a")
    assert response.status_code == 201
    assert response.json()["filename"] == "passwd.m4a"
    stored = [p for p in Path(storage_dir).rglob("*") if p.is_file()]
    assert len(stored) == 1
    assert storage_dir in stored[0].parents


def test_transcription_failure_is_recorded(client, study_id, storage_dir):
    class Broken:
        def transcribe(self, audio):
            raise RuntimeError("speech service unavailable")

    app.dependency_overrides[get_transcriber] = lambda: Broken()
    material = upload(client, study_id).json()

    assert material["status"] == "failed"
    assert material["error"] == "speech service unavailable"
    assert material["segments"] == []


def test_reprocessing_replaces_segments(client, study_id, storage_dir):
    class OneLine:
        def transcribe(self, audio):
            return [Segment("Teacher", 0, 1000, "Good morning.")]

    material_id = upload(client, study_id).json()["id"]
    assert len(client.get(f"/materials/{material_id}").json()["segments"]) == 3

    db = next(app.dependency_overrides[get_db]())
    process_material(material_id, db, LocalStorage(str(storage_dir)), OneLine())

    segments = client.get(f"/materials/{material_id}").json()["segments"]
    assert [s["text"] for s in segments] == ["Good morning."]


def test_unknown_study_or_material_returns_404(client, storage_dir):
    assert upload(client, "does-not-exist").status_code == 404
    assert client.get("/studies/does-not-exist/materials").status_code == 404
    assert client.get("/materials/does-not-exist").status_code == 404
