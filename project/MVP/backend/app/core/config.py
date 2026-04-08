# 配置管理模块
# 这里统一从环境变量和 .env 文件读取配置，并在启动期做硬约束校验
from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 固定模型常量
# 这些值属于系统契约的一部分，后续索引、检索、向量库结构都依赖它们。
PINNED_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
PINNED_EMBEDDING_DIMENSIONS = 1536
PINNED_RERANK_MODEL = "Qwen/Qwen3-Reranker-8B"


class Settings(BaseSettings):
    # ============ DeepSeek 配置 ============
    # 主问答链路固定使用 DeepSeek 官方 API。
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek 官方 API Key",
        validation_alias=AliasChoices(
            "deepseek_api_key",
            "llm_api_key",
            "DEEPSEEK_API_KEY",
            "LLM_API_KEY",
        ),
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek 官方 API Base URL",
        validation_alias=AliasChoices(
            "deepseek_base_url",
            "llm_base_url",
            "DEEPSEEK_BASE_URL",
            "LLM_BASE_URL",
        ),
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek 主问答模型",
        validation_alias=AliasChoices(
            "deepseek_model",
            "llm_model",
            "DEEPSEEK_MODEL",
            "LLM_MODEL",
        ),
    )
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="问答温度")
    llm_max_tokens: int = Field(default=2048, ge=1, description="问答最大输出 token")

    # ============ SiliconFlow 配置 ============
    # Embedding 与 Rerank 统一走 SiliconFlow，避免不同服务商混用导致契约漂移。
    siliconflow_api_key: str = Field(
        default="",
        description="SiliconFlow API Key",
        validation_alias=AliasChoices(
            "siliconflow_api_key",
            "embedding_api_key",
            "rerank_api_key",
            "SILICONFLOW_API_KEY",
            "EMBEDDING_API_KEY",
            "RERANK_API_KEY",
        ),
    )
    siliconflow_base_url: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="SiliconFlow API Base URL",
        validation_alias=AliasChoices(
            "siliconflow_base_url",
            "embedding_base_url",
            "SILICONFLOW_BASE_URL",
            "EMBEDDING_BASE_URL",
        ),
    )

    # ============ Embedding / Rerank 固定契约 ============
    # 这里不是“推荐值”，而是“系统硬约束”。
    # 一旦模型名或维度漂移，历史向量、检索结果和索引结构都会失去一致性。
    embedding_model: str = Field(
        default=PINNED_EMBEDDING_MODEL,
        description="固定的 Embedding 模型",
        validation_alias=AliasChoices(
            "embedding_model",
            "EMBEDDING_MODEL",
        ),
    )
    embedding_dimensions: int = Field(
        default=PINNED_EMBEDDING_DIMENSIONS,
        description="固定的 Embedding 向量维度",
        validation_alias=AliasChoices(
            "embedding_dimensions",
            "embedding_dimension",
            "EMBEDDING_DIMENSIONS",
            "EMBEDDING_DIMENSION",
        ),
    )
    embedding_batch_size: int = Field(default=32, ge=1, description="批量嵌入大小")
    rerank_model: str = Field(
        default=PINNED_RERANK_MODEL,
        description="固定的 Rerank 模型",
        validation_alias=AliasChoices(
            "rerank_model",
            "RERANK_MODEL",
        ),
    )

    # ============ MinerU 配置 ============
    # 这里只保留占位与基础调度参数，后续任务再接真正链路。
    mineru_api_key: str = Field(default="", description="MinerU API Key")
    mineru_base_url: str = Field(
        default="https://mineru.net/api/v4",
        description="MinerU API Base URL",
    )
    mineru_poll_interval: int = Field(default=5, ge=1, description="MinerU 轮询间隔（秒）")
    mineru_timeout: int = Field(default=300, ge=1, description="MinerU 最大等待时间（秒）")

    # ============ ChromaDB 配置 ============
    chroma_persist_dir: str = Field(
        default="./data/chroma",
        description="ChromaDB 本地持久化路径",
    )
    chroma_collection_name: str = Field(
        default="papers",
        description="ChromaDB 集合名称",
    )

    # ============ BM25 配置 ============
    bm25_index_path: str = Field(
        default="./data/bm25_index.json",
        description="BM25 索引文件路径",
    )

    # ============ SQLite 配置 ============
    sqlite_db_path: str = Field(
        default="./data/app.db",
        description="SQLite 数据库路径",
    )

    # ============ 检索配置 ============
    retrieval_vector_top_k: int = Field(default=30, ge=1, description="向量检索召回数")
    retrieval_bm25_top_k: int = Field(default=30, ge=1, description="BM25 检索召回数")
    retrieval_final_top_k: int = Field(default=10, ge=1, description="最终返回数")
    retrieval_rrf_k: int = Field(default=60, ge=1, description="RRF 融合参数 k")

    # ============ 应用配置 ============
    app_host: str = Field(default="127.0.0.1", description="服务监听地址")
    app_port: int = Field(default=8000, ge=1, le=65535, description="服务监听端口")
    app_debug: bool = Field(default=False, description="是否开启调试模式")

    # BaseSettings 配置
    # populate_by_name 让字段名可直接用于测试与代码内构造。
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_pinned_model_contract(self) -> "Settings":
        """校验模型契约，防止向量维度和模型漂移污染索引。"""
        if self.embedding_model != PINNED_EMBEDDING_MODEL:
            raise ValueError(f"EMBEDDING_MODEL 必须固定为 {PINNED_EMBEDDING_MODEL}")

        if self.embedding_dimensions != PINNED_EMBEDDING_DIMENSIONS:
            raise ValueError(f"EMBEDDING_DIMENSIONS 必须固定为 {PINNED_EMBEDDING_DIMENSIONS}")

        if self.rerank_model != PINNED_RERANK_MODEL:
            raise ValueError(f"RERANK_MODEL 必须固定为 {PINNED_RERANK_MODEL}")

        return self

    # ============ 旧字段兼容层 ============
    # Task 1 只允许改 config.py，因此这里保留旧属性，避免现有客户端与路由同时崩掉。
    @property
    def llm_api_key(self) -> str:
        """兼容旧字段名，映射到 DeepSeek API Key。"""
        return self.deepseek_api_key

    @property
    def llm_base_url(self) -> str:
        """兼容旧字段名，映射到 DeepSeek Base URL。"""
        return self.deepseek_base_url

    @property
    def llm_model(self) -> str:
        """兼容旧字段名，映射到 DeepSeek 模型。"""
        return self.deepseek_model

    @property
    def embedding_api_key(self) -> str:
        """兼容旧字段名，Embedding 统一复用 SiliconFlow API Key。"""
        return self.siliconflow_api_key

    @property
    def embedding_base_url(self) -> str:
        """兼容旧字段名，Embedding 直接使用 SiliconFlow Base URL。"""
        return self.siliconflow_base_url.rstrip("/")

    @property
    def embedding_dimension(self) -> int:
        """兼容旧字段名，映射到新的复数形式字段。"""
        return self.embedding_dimensions

    @property
    def rerank_api_key(self) -> str:
        """兼容旧字段名，Rerank 统一复用 SiliconFlow API Key。"""
        return self.siliconflow_api_key

    @property
    def rerank_base_url(self) -> str:
        """兼容旧字段名，拼出旧客户端需要的 /rerank 终端地址。"""
        return f"{self.siliconflow_base_url.rstrip('/')}/rerank"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例（缓存），避免每次请求重复解析环境变量。"""
    return Settings()
