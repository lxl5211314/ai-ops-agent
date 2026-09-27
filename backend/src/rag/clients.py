from contextlib import suppress
from functools import lru_cache

from core.config import get_settings


class MilvusStore:
    def __init__(self, uri: str, collection: str, dim: int):
        self.uri = uri
        self.collection = collection
        self.dim = dim
        self._client = None

    def client(self):
        if self._client is None:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=self.uri)
        return self._client

    def ensure_collection(self):
        from pymilvus import DataType, MilvusClient

        c = self.client()
        if c.has_collection(self.collection):
            return
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("chunk_text", DataType.VARCHAR, max_length=8192)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("heading", DataType.VARCHAR, max_length=512)
        schema.add_field("category", DataType.VARCHAR, max_length=64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.dim)
        index_params = MilvusClient.prepare_index_params()
        index_params.add_index("vector", metric_type="COSINE")
        c.create_collection(self.collection, schema=schema, index_params=index_params)

    def insert(self, rows: list[dict], vectors: list[list[float]]):
        self.ensure_collection()
        data = [{**row, "vector": vec} for row, vec in zip(rows, vectors, strict=False)]
        self.client().insert(self.collection, data)

    def search(self, vector: list[float], top_k: int = 5) -> list[dict]:
        self.ensure_collection()
        res = self.client().search(
            self.collection,
            data=[vector],
            limit=top_k,
            output_fields=["chunk_text", "document_id", "heading", "category"],
        )
        out = []
        for hits in res:
            for hit in hits:
                entity = hit.get("entity", {})
                out.append(
                    {
                        "chunk_text": entity.get("chunk_text", ""),
                        "document_id": entity.get("document_id", ""),
                        "heading": entity.get("heading", ""),
                        "category": entity.get("category", ""),
                        "score": float(hit.get("score", 0.0)),
                    }
                )
        return out

    def delete_document(self, document_id: str):
        with suppress(Exception):
            self.client().delete(self.collection, filter=f'document_id == "{document_id}"')

    def ping(self) -> bool:
        try:
            self.client().has_collection(self.collection)
            return True
        except Exception:  # noqa: BLE001
            return False


class Neo4jStore:
    def __init__(self, uri: str, user: str, password: str):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None

    def driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def write_graph(self, document_id: str, entities: list[dict], relations: list[dict]):
        with self.driver().session() as session:
            for ent in entities:
                session.run(
                    "MERGE (e:Entity {name: $name, document_id: $doc}) "
                    "SET e.type = $type, e.document_id = $doc",
                    name=ent.get("name", "").strip(),
                    type=ent.get("type", "Unknown"),
                    doc=document_id,
                )
            for rel in relations:
                session.run(
                    "MATCH (a:Entity {name: $s, document_id: $doc}) "
                    "MATCH (b:Entity {name: $o, document_id: $doc}) "
                    "MERGE (a)-[r:RELATION {name: $rel}]->(b)",
                    s=rel.get("subject", "").strip(),
                    o=rel.get("object", "").strip(),
                    rel=rel.get("relation", "related_to"),
                    doc=document_id,
                )

    def expand(self, keywords: list[str], limit: int = 8) -> list[str]:
        if not keywords:
            return []
        keywords = keywords[:8]
        where = " OR ".join([f"e.name CONTAINS $k{i}" for i in range(len(keywords))])
        params = {f"k{i}": kw for i, kw in enumerate(keywords)}
        params["limit"] = limit
        query = (
            f"MATCH (e:Entity) WHERE {where} "
            "OPTIONAL MATCH (e)-[r:RELATION]-(n:Entity) "
            "RETURN e.name AS a, r.name AS rel, n.name AS b LIMIT $limit"
        )
        out = []
        with self.driver().session() as session:
            for record in session.run(query, **params):
                a, rel, b = record["a"], record["rel"], record["b"]
                if rel and b:
                    out.append(f"{a} -[{rel}]-> {b}")
                else:
                    out.append(a)
        return out

    def delete_document(self, document_id: str):
        with suppress(Exception), self.driver().session() as session:
            session.run("MATCH (e:Entity {document_id: $doc}) DETACH DELETE e", doc=document_id)

    def ping(self) -> bool:
        try:
            self.driver().verify_connectivity()
            return True
        except Exception:  # noqa: BLE001
            return False


class MinioStore:
    def __init__(self, endpoint: str, access: str, secret: str, secure: bool):
        self.endpoint = endpoint
        self.access = access
        self.secret = secret
        self.secure = secure
        self._client = None

    def client(self):
        if self._client is None:
            from minio import Minio

            self._client = Minio(
                self.endpoint, access_key=self.access, secret_key=self.secret, secure=self.secure
            )
        return self._client

    def ensure_bucket(self, bucket: str):
        c = self.client()
        if not c.bucket_exists(bucket):
            c.make_bucket(bucket)

    def put(
        self,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ):
        self.ensure_bucket(bucket)
        from io import BytesIO

        self.client().put_object(bucket, object_name, BytesIO(data), len(data), content_type)

    def get(self, bucket: str, object_name: str) -> bytes:
        resp = self.client().get_object(bucket, object_name)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def remove(self, bucket: str, object_name: str):
        with suppress(Exception):
            self.client().remove_object(bucket, object_name)

    def ping(self) -> bool:
        try:
            return self.client().list_buckets() is not None
        except Exception:  # noqa: BLE001
            return False


class RAG:
    def __init__(self, settings):
        self.milvus = MilvusStore(
            settings.milvus_uri, settings.milvus_collection, settings.embedding_dim
        )
        self.neo4j = Neo4jStore(
            settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password
        )
        self.minio = MinioStore(
            settings.minio_endpoint,
            settings.minio_access_key,
            settings.minio_secret_key,
            settings.minio_secure,
        )
        self.bucket_docs = settings.minio_bucket_docs
        self.bucket_archives = settings.minio_bucket_archives

    def health(self) -> dict:
        return {
            "milvus": "ok" if self.milvus.ping() else "degraded",
            "neo4j": "ok" if self.neo4j.ping() else "degraded",
            "minio": "ok" if self.minio.ping() else "degraded",
        }


@lru_cache
def get_rag() -> RAG:
    return RAG(get_settings())
