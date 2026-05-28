"""配置模块

读取用户配置和系统默认配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class DataLayerConfig:
    """data_layer 配置"""
    # VLM 配置（默认使用 api.coro0.top 代理）
    vlm_api_key: str = ""
    vlm_base_url: str = "https://api.coro0.top/v1"
    vlm_model: str = "qwen3-vl:235b"
    vlm_timeout: int = 60

    # Embedding 配置（默认使用硅基流动）
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "Qwen/Qwen3-Embedding-4B"
    embedding_dimensions: int = 1536
    embedding_timeout: int = 30
    embedding_batch_size: int = 32
    embedding_max_concurrency: int = 5

    # Rerank 配置（默认使用硅基流动）
    rerank_api_key: str = ""
    rerank_base_url: str = "https://api.siliconflow.cn/v1"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # ChromaDB 配置
    chroma_path: str = "./data/chroma_db"
    chroma_dimension: int = 1536

    # BM25 配置
    bm25_index_path: str = "./data/bm25_index"

    # 文件管理配置
    papers_dir: str = "./data/papers"
    parsed_dir: str = "./data/parsed"
    backups_dir: str = "./data/backups"

    # 软删除配置
    soft_delete_retention_days: int = 7


def load_config() -> DataLayerConfig:
    """加载配置

    优先级：环境变量 > .env 文件 > 默认值
    """
    # 尝试从 .env 文件加载
    _load_dotenv()

    return DataLayerConfig(
        # VLM
        vlm_api_key=os.getenv("VLM_API_KEY", os.getenv("My_ProxyAPI_KEY", "")),
        vlm_base_url=os.getenv("VLM_BASE_URL", "https://api.coro0.top/v1"),
        vlm_model=os.getenv("VLM_MODEL", "qwen3-vl:235b"),
        vlm_timeout=int(os.getenv("VLM_TIMEOUT", "60")),

        # Embedding
        embedding_api_key=os.getenv("SILICONFLOW_API_KEY", os.getenv("EMBEDDING_API_KEY", "")),
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B"),
        embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
        embedding_timeout=int(os.getenv("EMBEDDING_TIMEOUT", "30")),
        embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
        embedding_max_concurrency=int(os.getenv("EMBEDDING_MAX_CONCURRENCY", "5")),

        # Rerank
        rerank_api_key=os.getenv("SILICONFLOW_API_KEY", os.getenv("RERANK_API_KEY", "")),
        rerank_base_url=os.getenv("RERANK_BASE_URL", "https://api.siliconflow.cn/v1"),
        rerank_model=os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"),

        # ChromaDB
        chroma_path=os.getenv("CHROMA_PATH", "./data/chroma_db"),
        chroma_dimension=int(os.getenv("CHROMA_DIMENSIONS", "1536")),

        # BM25
        bm25_index_path=os.getenv("BM25_INDEX_PATH", "./data/bm25_index"),

        # 文件管理
        papers_dir=os.getenv("PAPERS_DIR", "./data/papers"),
        parsed_dir=os.getenv("PARSED_DIR", "./data/parsed"),
        backups_dir=os.getenv("BACKUPS_DIR", "./data/backups"),

        # 软删除
        soft_delete_retention_days=int(os.getenv("SOFT_DELETE_RETENTION_DAYS", "7")),
    )


def _load_dotenv():
    """加载 .env 文件"""
    # config/ -> data_persistence/ -> data_layer/ -> app/ -> backend/
    env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
