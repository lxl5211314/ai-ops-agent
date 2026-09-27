import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", f"..{os.sep}.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://xiaolong:xiaolong@localhost:3306/xiaolong?charset=utf8mb4"
    auto_create_tables: bool = True

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "kb_chunks"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "xiaolong-dev"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "xiaolong"
    minio_secret_key: str = "xiaolong123"
    minio_secure: bool = False
    minio_bucket_docs: str = "kb-documents"
    minio_bucket_archives: str = "source-archives"

    ingest_allowed_roots: str = ""
    data_dir: str = "./data"
    cors_origins: str = "http://localhost:5173"

    @property
    def allowed_roots(self) -> list[str]:
        raw = self.ingest_allowed_roots
        if ";" in raw and os.pathsep != ";":
            raw = raw.replace(";", os.pathsep)
        parts = raw.split(os.pathsep) if raw else []
        return [r.strip().rstrip("/\\") for r in parts if r.strip()]

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
