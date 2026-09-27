def test_create_list_get_delete_conversation(client):
    created = client.post("/api/v1/conversations", json={"title": "排障会话"})
    assert created.status_code == 201
    cid = created.json()["id"]

    listed = client.get("/api/v1/conversations").json()
    assert any(c["id"] == cid for c in listed)

    detail = client.get(f"/api/v1/conversations/{cid}")
    assert detail.status_code == 200
    assert detail.json()["messages"] == []

    assert client.delete(f"/api/v1/conversations/{cid}").status_code == 204
    assert client.get(f"/api/v1/conversations/{cid}").status_code == 404


def test_post_message_validation_and_stream_url(client):
    conv = client.post("/api/v1/conversations", json={}).json()
    cid = conv["id"]

    empty = client.post(f"/api/v1/conversations/{cid}/messages", json={"content": ""})
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "VALIDATION"

    blank = client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "   "})
    assert blank.status_code == 400

    ok = client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "磁盘满了怎么办"})
    assert ok.status_code == 202
    body = ok.json()
    assert body["stream_url"].endswith("/stream")
    assert f"/conversations/{cid}/messages/{body['message_id']}" in body["stream_url"]


def test_missing_conversation_404(client):
    resp = client.get("/api/v1/conversations/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
