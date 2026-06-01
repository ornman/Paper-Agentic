from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _APP_ROOT.parent
_DATA_ROOT = _BACKEND_ROOT / "data"


class BackendSettings(BaseSettings):
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")
    llm_timeout: float = Field(default=120.0, alias="LLM_TIMEOUT")
    llm_fallback_models: str = Field(default="", alias="LLM_FALLBACK_MODELS")
    llm_context_window: int = Field(default=0, alias="LLM_CONTEXT_WINDOW")

    reflection_api_key: str = Field(default="", alias="REFLECTION_API_KEY")
    reflection_base_url: str = Field(default="", alias="REFLECTION_BASE_URL")
    reflection_model: str = Field(default="", alias="REFLECTION_MODEL")
    reflection_temperature: float = Field(default=0.3, alias="REFLECTION_TEMPERATURE")
    reflection_timeout: float = Field(default=60.0, alias="REFLECTION_TIMEOUT")

    vlm_api_key: str = Field(default="", alias="VLM_API_KEY")
    vlm_base_url: str = Field(default="", alias="VLM_BASE_URL")
    vlm_model: str = Field(default="", alias="VLM_MODEL")
    vlm_timeout: float = Field(default=120.0, alias="VLM_TIMEOUT")

    mineru_api_key: str = Field(default="", alias="MINERU_API_KEY")
    mineru_base_url: str = Field(default="", alias="MINERU_BASE_URL")
    mineru_poll_interval: int = Field(default=5, alias="MINERU_POLL_INTERVAL")
    mineru_timeout: int = Field(default=300, alias="MINERU_TIMEOUT")
    mineru_max_retries: int = Field(default=3, alias="MINERU_MAX_RETRIES")
    mineru_max_pages_per_chunk: int = Field(default=180, alias="MINERU_MAX_PAGES_PER_CHUNK")
    mineru_max_per_key: int = Field(default=2, alias="MINERU_MAX_PER_KEY")

    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="Qwen/Qwen3-Embedding-4B", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(
        default=1536,
        validation_alias=AliasChoices("EMBEDDING_DIMENSION", "EMBEDDING_DIMENSIONS"),
    )
    embedding_timeout: float = Field(default=60.0, alias="EMBEDDING_TIMEOUT")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")
    embedding_max_concurrency: int = Field(default=8, alias="EMBEDDING_MAX_CONCURRENCY")
    embedding_context_window: int = Field(default=0, alias="EMBEDDING_CONTEXT_WINDOW")

    rerank_api_key: str = Field(default="", alias="RERANK_API_KEY")
    rerank_base_url: str = Field(default="", alias="RERANK_BASE_URL")
    rerank_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANK_MODEL")
    rerank_timeout: float = Field(default=30.0, alias="RERANK_TIMEOUT")

    chroma_data_dir: Path = Field(default=_DATA_ROOT / "chroma_db", alias="CHROMA_DATA_DIR")
    bm25_data_dir: Path = Field(default=_DATA_ROOT / "bm25_index", alias="BM25_DATA_DIR")
    backup_dir: Path = Field(default=_DATA_ROOT / "backups", alias="BACKUP_DIR")
    papers_dir: Path = Field(default=_DATA_ROOT / "papers", alias="PAPERS_DIR")
    parsed_dir: Path = Field(default=_DATA_ROOT / "parsed", alias="PARSED_DIR")
    uploads_dir: Path = Field(default=_DATA_ROOT / "uploads", alias="UPLOADS_DIR")
    app_db_path: Path = Field(default=_DATA_ROOT / "app.db", alias="APP_DB_PATH")

    chunk_max_context: int = Field(default=32000, alias="CHUNK_MAX_CONTEXT")
    chunk_target_size: int = Field(default=24000, alias="CHUNK_TARGET_SIZE")
    chunk_overlap_buffer: int = Field(default=8000, alias="CHUNK_OVERLAP_BUFFER")

    context_window_tokens: int = Field(default=32000, alias="CONTEXT_WINDOW_TOKENS")
    max_output_tokens: int = Field(default=4096, alias="MAX_OUTPUT_TOKENS")

    # ── 检索参数 ──
    retrieval_topk_dense: int = Field(default=20, alias="RETRIEVAL_TOPK_DENSE")
    retrieval_topk_sparse: int = Field(default=20, alias="RETRIEVAL_TOPK_SPARSE")
    retrieval_max_distance: float = Field(default=2.0, alias="RETRIEVAL_MAX_DISTANCE")
    retrieval_rrf_k: int = Field(default=60, alias="RETRIEVAL_RRF_K")

    # ── VLM ──
    vlm_max_tokens: int = Field(default=1024, alias="VLM_MAX_TOKENS")
    vlm_max_retries: int = Field(default=3, alias="VLM_MAX_RETRIES")
    vlm_retry_base_delay_ms: int = Field(default=1000, alias="VLM_RETRY_BASE_DELAY_MS")
    vlm_retry_jitter_ms: int = Field(default=300, alias="VLM_RETRY_JITTER_MS")

    # ── 语义切分 ──
    chunk_min_tokens: int = Field(default=128, alias="CHUNK_MIN_TOKENS")
    chunk_max_tokens: int = Field(default=512, alias="CHUNK_MAX_TOKENS")
    chunk_overlap_ratio: float = Field(default=0.10, alias="CHUNK_OVERLAP_RATIO")
    chunk_similarity_threshold: float = Field(default=0.3, alias="CHUNK_SIMILARITY_THRESHOLD")
    chunk_embedding_window: int = Field(default=3, alias="CHUNK_EMBEDDING_WINDOW")

    # ── 会话压缩 ──
    compact_max_summary_tokens: int = Field(default=500, alias="COMPACT_MAX_SUMMARY_TOKENS")
    compact_fallback_keep_recent: int = Field(default=6, alias="COMPACT_FALLBACK_KEEP_RECENT")
    compact_trigger_ratio: float = Field(default=0.05, alias="COMPACT_TRIGGER_RATIO")

    # ── Reflection ──
    reflection_max_rounds: int = Field(default=3, alias="REFLECTION_MAX_ROUNDS")
    reflection_max_direction_switches: int = Field(default=2, alias="REFLECTION_MAX_DIRECTION_SWITCHES")

    # ── 软删除 ──
    soft_delete_retention_days: int = Field(default=7, alias="SOFT_DELETE_RETENTION_DAYS")

    # ── 窗口估算 ──
    avg_message_tokens: int = Field(default=500, alias="AVG_MESSAGE_TOKENS")
    system_prompt_tokens: int = Field(default=2000, alias="SYSTEM_PROMPT_TOKENS")

    # ── UI/输入 ──
    source_snippet_max_length: int = Field(default=220, alias="SOURCE_SNIPPET_MAX_LENGTH")
    title_max_length: int = Field(default=20, alias="TITLE_MAX_LENGTH")

    # ── 输入权重 ──
    weight_prompt_three_source: float = Field(default=0.5, alias="WEIGHT_PROMPT_THREE_SOURCE")
    weight_selection_three_source: float = Field(default=0.3, alias="WEIGHT_SELECTION_THREE_SOURCE")
    weight_written_three_source: float = Field(default=0.2, alias="WEIGHT_WRITTEN_THREE_SOURCE")
    weight_selection_two_source: float = Field(default=0.7, alias="WEIGHT_SELECTION_TWO_SOURCE")
    weight_written_two_source: float = Field(default=0.3, alias="WEIGHT_WRITTEN_TWO_SOURCE")

    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def llm_fallback_list(self) -> list[str]:
        if not self.llm_fallback_models.strip():
            return []
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip() and self.llm_base_url.strip() and self.llm_model.strip())

    @property
    def embedding_configured(self) -> bool:
        return bool(self.embedding_api_key.strip() and self.embedding_base_url.strip() and self.embedding_model.strip())

    @property
    def rerank_configured(self) -> bool:
        return bool(self.rerank_api_key.strip() and self.rerank_base_url.strip() and self.rerank_model.strip())

    @property
    def reflection_configured(self) -> bool:
        return bool(self.reflection_api_key.strip() and self.reflection_base_url.strip() and self.reflection_model.strip())

    def ensure_runtime_dirs(self) -> None:
        for path in (
            self.chroma_data_dir,
            self.bm25_data_dir,
            self.backup_dir,
            self.papers_dir,
            self.parsed_dir,
            self.uploads_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> BackendSettings:
    return BackendSettings()
