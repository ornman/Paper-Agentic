from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM 对话（Kimi Coding API，256K 上下文窗口）
    kimi_api_key: str = Field(default="", alias="KIMI_API_KEY")
    kimi_base_url: str = "https://api.kimi.com/coding/v1/messages"
    kimi_model: str = "K2.6-code-preview"

    # Embedding（硅基流动）—— 复用 .env 的 EMBEDDING_API_KEY
    siliconflow_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_model: str = Field(default="Qwen/Qwen3-Embedding-8B", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSION")

    # PDF 解析
    mineru_api_key: str = Field(default="", alias="MINERU_API_KEY")
    mineru_base_url: str = Field(default="https://mineru.net/api/v4", alias="MINERU_BASE_URL")
    mineru_poll_interval: float = 3.0
    mineru_timeout: float = 300.0

    # 存储
    chroma_data_dir: str = "./data/chroma_db"
    backup_dir: str = "./data/backups"

    # 切分策略
    chunk_max_context: int = 32000
    chunk_target_size: int = 24000
    chunk_overlap_buffer: int = 8000

    model_config = {"env_file": ".env", "extra": "ignore", "populate_by_name": True}


def get_settings() -> Settings:
    return Settings()
