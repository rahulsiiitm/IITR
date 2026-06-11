from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default=PROJECT_ROOT / "data" / "raw")
    vector_db_dir: Path = Field(default=PROJECT_ROOT / "vector_db")

    embedding_model: str = "BAAI/bge-base-en-v1.5"
    rerank_model: str = "BAAI/bge-reranker-base"
    ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"
    ollama_url: str = "http://localhost:11434/api/chat"

    top_k: int = 15
    subquestion_top_k: int = 10
    rerank_top_k: int = 5
    rerank_top_k_multi: int = 5
    chunk_size: int = 2000
    chunk_overlap: int = 250
    confidence_threshold: float = -5.0

    api_port: int = 45123
    api_key: str | None = None
    
    database_url: str = "postgresql+asyncpg://sutra_admin:sutra_secure_password@localhost:5432/sutra_db"

    debug: bool = False
    log_level: str = "INFO"
    cors_origins: str = (
        "http://localhost:3000,http://localhost:8080,"
        "http://127.0.0.1:8080,http://127.0.0.1:5500,http://localhost:5500"
    )

    @property
    def faiss_index_path(self) -> Path:
        return self.vector_db_dir / "indexes" / "faiss.index"

    @property
    def chunks_metadata_path(self) -> Path:
        return self.vector_db_dir / "metadata" / "chunks.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()


