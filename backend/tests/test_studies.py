def test_create_and_list_study(client):
    created = client.post(
        "/studies",
        json={"title": "Novice teacher study", "research_questions": "What do teachers notice?"},
    )
    assert created.status_code == 201
    study = created.json()
    assert study["participants"] == []

    listed = client.get("/studies").json()
    assert [s["id"] for s in listed] == [study["id"]]


def test_add_participant(client):
    study = client.post("/studies", json={"title": "Pilot"}).json()

    added = client.post(f"/studies/{study['id']}/participants", json={"label": "T07"})
    assert added.status_code == 201

    fetched = client.get(f"/studies/{study['id']}").json()
    assert [p["label"] for p in fetched["participants"]] == ["T07"]


def test_empty_title_is_rejected(client):
    assert client.post("/studies", json={"title": ""}).status_code == 422


def test_unknown_study_returns_404(client):
    assert client.get("/studies/does-not-exist").status_code == 404
    assert (
        client.post("/studies/does-not-exist/participants", json={"label": "T01"}).status_code
        == 404
    )
