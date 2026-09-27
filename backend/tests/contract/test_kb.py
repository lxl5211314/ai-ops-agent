def test_upload_document_invalid_category(client):
    resp = client.post(
        "/api/v1/kb/documents",
        data={"category": "unknown"},
        files={"file": ("a.md", b"# hi", "text/markdown")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION"


def test_upload_document_empty_file(client):
    resp = client.post(
        "/api/v1/kb/documents",
        data={"category": "ops_knowledge"},
        files={"file": ("empty.md", b"", "text/markdown")},
    )
    assert resp.status_code == 400


def test_upload_document_object_store_failure(client, fake_rag):
    fake_rag.minio.fail = True
    try:
        resp = client.post(
            "/api/v1/kb/documents",
            data={"category": "ops_knowledge"},
            files={"file": ("doc.md", b"# content", "text/markdown")},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "UNPROCESSABLE"
    finally:
        fake_rag.minio.fail = False


def test_upload_ingest_and_index(client, wait_until):
    content = "# 运维手册\n\n磁盘空间不足时，先清理 /var/log 下的滚动日志，再评估扩容。\n"
    resp = client.post(
        "/api/v1/kb/documents",
        data={"category": "ops_knowledge", "title": "磁盘清理手册"},
        files={"file": ("disk.md", content.encode(), "text/markdown")},
    )
    assert resp.status_code == 202
    doc_id = resp.json()["id"]
    assert resp.json()["status"] == "PENDING"

    def indexed():
        doc = client.get(f"/api/v1/kb/documents/{doc_id}").json()
        return doc if doc["status"] != "PENDING" else None

    doc = wait_until(indexed)
    assert doc["status"] == "INDEXED", doc
    assert doc["chunk_count"] >= 1
    assert doc["job"]["stage"] == "DONE"

    listed = client.get("/api/v1/kb/documents").json()
    assert any(d["id"] == doc_id for d in listed)

    assert client.delete(f"/api/v1/kb/documents/{doc_id}").status_code == 204
    assert client.get(f"/api/v1/kb/documents/{doc_id}").status_code == 404
