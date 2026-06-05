from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DocumentConfig:
    """Static registry for indexed documents (single-PDF phase)."""

    filename: str = "phd_regulations_2026.pdf"
    title: str = "PhD Regulations"
    category: str = "academic"
    year: int = 2026


DOCUMENT_REGISTRY: dict[str, DocumentConfig] = {
    "phd_regulations_2026": DocumentConfig(),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pdf_path: Path = Field(default=PROJECT_ROOT / "data" / "raw" / "phd_regulations_2026.pdf")
    vector_db_dir: Path = Field(default=PROJECT_ROOT / "vector_db")

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ollama_model: str = "mistral:latest"
    ollama_url: str = "http://localhost:11434/api/generate"

    top_k: int = 15
    subquestion_top_k: int = 6
    rerank_top_k: int = 6
    rerank_top_k_multi: int = 8
    chunk_size: int = 1000
    chunk_overlap: int = 250
    confidence_threshold: float = -5.0

    api_port: int = 45123
    api_key: str = "dev_key_123"

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


def get_document_config(document_key: str = "phd_regulations_2026") -> DocumentConfig:
    return DOCUMENT_REGISTRY[document_key]
