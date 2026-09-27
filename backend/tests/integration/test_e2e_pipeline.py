"""End-to-end pipeline test with real infrastructure (MySQL/Milvus/Neo4j/MinIO).

Requires Docker. Enable with RUN_INTEGRATION=1 after `docker compose up -d`.
Skipped by default so the contract/unit suite stays runnable without infra.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="set RUN_INTEGRATION=1 with docker compose infra running",
)


def test_health_all_ok_when_infra_up(client):
    health = client.get("/api/v1/health").json()
    assert health["status"] == "ok"
    assert health["mysql"] == "ok"
    assert health["milvus"] == "ok"
    assert health["neo4j"] == "ok"
    assert health["minio"] == "ok"


def test_ingest_search_chat_flow(client, wait_until):
    content = "# 缓存故障\n\nRedis 主从切换期间可能出现短暂不可用，需检查哨兵状态。\n"
    resp = client.post(
        "/api/v1/kb/documents",
        data={"category": "ops_knowledge", "title": "缓存故障处置"},
        files={"file": ("cache.md", content.encode(), "text/markdown")},
    )
    assert resp.status_code == 202
    doc_id = resp.json()["id"]

    def indexed():
        doc = client.get(f"/api/v1/kb/documents/{doc_id}").json()
        return doc if doc["status"] in ("INDEXED", "FAILED") else None

    doc = wait_until(indexed, timeout=60)
    assert doc["status"] == "INDEXED", doc

    conv = client.post("/api/v1/conversations", json={}).json()
    msg = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "Redis 切换期间不可用怎么办？"},
    ).json()
    with client.stream("GET", msg["stream_url"]) as stream:
        text = "".join(
            line for line in (chunk.decode() for chunk in stream.iter_bytes()) if "delta" in line
        )
    assert text
