"""Config & Embedding 模块测试

CONF-U01: 环境变量优先级
CONF-U02: .env 路径验证
"""

from __future__ import annotations

import os
import pytest

from app.data_layer.data_persistence.config import DataLayerConfig, load_config


class TestConfU01:
    """环境变量优先级"""

    def test_load_config_returns_data_layer_config(self):
        """load_config 返回 DataLayerConfig"""
        config = load_config()
        assert isinstance(config, DataLayerConfig)

    def test_default_values(self):
        """默认值存在"""
        config = DataLayerConfig()
        assert config.vlm_base_url == "https://api.coro0.top/v1"
        assert config.embedding_model == "Qwen/Qwen3-Embedding-4B"
        assert config.embedding_dimensions == 1536
        assert config.chroma_dimension == 1536
        assert config.soft_delete_retention_days == 7

    def test_env_var_overrides_default(self, monkeypatch):
        """环境变量覆盖默认值"""
        monkeypatch.setenv("VLM_MODEL", "custom-model")
        config = load_config()
        assert config.vlm_model == "custom-model"

    def test_siliconflow_api_key_from_env(self, monkeypatch):
        """SILICONFLOW_API_KEY 设置 embedding 和 rerank"""
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key-123")
        config = load_config()
        assert config.embedding_api_key == "test-key-123"
        assert config.rerank_api_key == "test-key-123"


class TestConfU02:
    """路径配置"""

    def test_chroma_path_configurable(self, monkeypatch):
        """ChromaDB 路径可配置"""
        monkeypatch.setenv("CHROMA_PATH", "/tmp/test_chroma")
        config = load_config()
        assert config.chroma_path == "/tmp/test_chroma"

    def test_bm25_path_configurable(self, monkeypatch):
        """BM25 路径可配置"""
        monkeypatch.setenv("BM25_INDEX_PATH", "/tmp/test_bm25")
        config = load_config()
        assert config.bm25_index_path == "/tmp/test_bm25"


class TestConfU03:
    """配置模块 .env 路径"""

    def test_dotenv_path_resolves_to_backend_root(self):
        """_load_dotenv 路径应解析到 backend/.env"""
        from app.data_layer.data_persistence.config.settings import _load_dotenv
        import inspect

        source = inspect.getsource(_load_dotenv)
        # 路径计算应该有 4 个 ".."（config -> data_persistence -> data_layer -> app -> backend）
        assert source.count('".."') >= 4 or source.count("'..'") >= 4, (
            "_load_dotenv 路径计算应该向上 4 层到达 backend/"
        )
