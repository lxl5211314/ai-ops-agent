import os
import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE.parent / "src"
sys.path.insert(0, str(SRC))

_TMP = Path(tempfile.mkdtemp(prefix="xiaolong_test_"))
FIXTURE_ROOT = BASE / "fixtures"
ALLOWED_ROOT = str(FIXTURE_ROOT.resolve())

_REAL_INFRA = os.environ.get("RUN_INTEGRATION") == "1"
if not _REAL_INFRA:
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}")
os.environ.setdefault("AUTO_CREATE_TABLES", "true")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("EMBEDDING_DIM", "8")
os.environ["INGEST_ALLOWED_ROOTS"] = ALLOWED_ROOT
os.environ.setdefault("DATA_DIR", str(_TMP / "data"))
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class FakeLLM:
    def __init__(self):
        self.settings = None

    async def stream_chat(self, messages, temperature=0.2):
        for part in ["原因分析：", "磁盘空间不足。", "\n解决方案：", "清理日志并扩容。"]:
            yield part

    async def chat_json(self, messages, temperature=0.1):
        prompt = messages[0]["content"]
        if "信息抽取器" in prompt:
            return {
                "entities": [{"name": "登录服务", "type": "服务"}],
                "relations": [{"subject": "登录服务", "relation": "使用", "object": "token"}],
            }
        import re

        match = re.search(r"### 文件: (\S+)", prompt)
        target = match.group(1) if match else "app.py"
        return {
            "locations": [
                {"file": target, "line_start": 1, "line_end": 2, "snippet": "user['token']"}
            ],
            "root_cause": "直接用下标访问 user['token']，当字典缺少 token 键时抛出 KeyError。",
            "fix_suggestion": "改用 user.get('token', '') 做安全取值，并在缺失时返回默认值。",
            "patch": (
                f"--- a/{target}\n"
                f"+++ b/{target}\n"
                "@@ -1,2 +1,2 @@\n"
                " def get_user_token(user):\n"
                "-    return user['token']\n"
                "+    return user.get('token', '')\n"
            ),
        }

    async def embed(self, texts):
        return [[0.1] * 8 for _ in texts]

    async def ping(self):
        return True


class FakeMinio:
    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.fail = False

    def put(self, bucket, object_name, data, content_type="application/octet-stream"):
        if self.fail:
            raise RuntimeError("minio down")
        self.store[f"{bucket}/{object_name}"] = data

    def get(self, bucket, object_name):
        return self.store[f"{bucket}/{object_name}"]

    def remove(self, bucket, object_name):
        self.store.pop(f"{bucket}/{object_name}", None)

    def ping(self):
        return not self.fail


class FakeMilvus:
    def __init__(self):
        self.rows: list[dict] = []

    def insert(self, rows, vectors):
        self.rows.extend(rows)

    def search(self, vector, top_k=5):
        return [
            {**row, "score": 1.0}
            for row in self.rows[:top_k]
        ]

    def delete_document(self, document_id):
        self.rows = [r for r in self.rows if r.get("document_id") != document_id]

    def ping(self):
        return True


class FakeNeo4j:
    def __init__(self):
        self.edges: list[str] = []

    def write_graph(self, document_id, entities, relations):
        for rel in relations:
            self.edges.append(f"{rel['subject']}-{rel['relation']}-{rel['object']}")

    def expand(self, keywords, limit=8):
        return self.edges[:limit]

    def delete_document(self, document_id):
        self.edges = []

    def ping(self):
        return True


class FakeRAG:
    def __init__(self):
        self.milvus = FakeMilvus()
        self.neo4j = FakeNeo4j()
        self.minio = FakeMinio()
        self.bucket_docs = "kb-documents"
        self.bucket_archives = "source-archives"

    def health(self):
        return {"milvus": "ok", "neo4j": "ok", "minio": "ok"}


@pytest.fixture(scope="session")
def fake_llm():
    return FakeLLM()


@pytest.fixture(scope="session")
def fake_rag():
    return FakeRAG()


@pytest.fixture(scope="session")
def client(fake_llm, fake_rag):
    import main
    from llm import get_llm
    from rag.clients import get_rag

    main.app.dependency_overrides[get_llm] = lambda: fake_llm
    if not _REAL_INFRA:
        main.app.dependency_overrides[get_rag] = lambda: fake_rag
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def wait_until():
    def _wait(predicate, timeout=10.0, interval=0.1):
        deadline = time.time() + timeout
        while time.time() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(interval)
        raise AssertionError("condition not met within timeout")

    return _wait
