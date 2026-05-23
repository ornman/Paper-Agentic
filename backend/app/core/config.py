from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _BACKEND_ROOT / "data"


class Settings(BaseSettings):
    # LLM 对话（OpenAI 兼容协议）
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")
    llm_timeout: float = Field(default=120.0, alias="LLM_TIMEOUT")

    # VLM 图片理解（可选独立配置，默认复用 LLM 配置）
    vlm_model: str = Field(default="", alias="VLM_MODEL")

    # Embedding
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="Qwen/Qwen3-Embedding-8B", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSION")

    # PDF 解析
    mineru_api_key: str = Field(default="", alias="MINERU_API_KEY")
    mineru_base_url: str = Field(default="https://mineru.net/api/v4", alias="MINERU_BASE_URL")
    mineru_poll_interval: float = 3.0
    mineru_timeout: float = 300.0

    # 存储
    chroma_data_dir: str = str(_DATA_DIR / "chroma_db")
    bm25_data_dir: str = str(_DATA_DIR / "bm25_index")
    backup_dir: str = str(_DATA_DIR / "backups")
    papers_dir: str = str(_DATA_DIR / "papers")
    uploads_dir: str = str(_DATA_DIR / "uploads")
    app_db_path: str = str(_DATA_DIR / "app.db")

    # 切分策略
    chunk_max_context: int = 32000
    chunk_target_size: int = 24000
    chunk_overlap_buffer: int = 8000

    model_config = {"env_file": str(_BACKEND_ROOT / ".env"), "extra": "ignore", "populate_by_name": True}


def get_settings() -> Settings:
    return Settings()
