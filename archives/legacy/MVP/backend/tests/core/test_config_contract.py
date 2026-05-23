# 配置契约测试
# Task 1 只验证配置层的硬约束，不扩展到其他业务模块
from pathlib import Path

from pydantic import ValidationError
import pytest

from app.core.config import Settings


def test_embedding_dimension_is_pinned_to_1536():
    """固定合法配置时，配置对象应能正常构建。"""
    settings = Settings(
        _env_file=None,
        embedding_model="Qwen/Qwen3-Embedding-8B",
        embedding_dimensions=1536,
    )

    assert settings.embedding_dimensions == 1536


def test_embedding_model_must_use_qwen3_embedding_8b():
    """如果 embedding 模型被改成其他值，必须立即报错。"""
    with pytest.raises(ValidationError, match="EMBEDDING_MODEL 必须固定为 Qwen/Qwen3-Embedding-8B"):
        Settings(
            _env_file=None,
            embedding_model="BAAI/bge-m3",
            embedding_dimensions=1536,
        )


def test_embedding_dimensions_must_stay_1536():
    """如果 embedding 维度被改掉，必须立即报错，防止后续索引污染。"""
    with pytest.raises(ValidationError, match="EMBEDDING_DIMENSIONS 必须固定为 1536"):
        Settings(
            _env_file=None,
            embedding_model="Qwen/Qwen3-Embedding-8B",
            embedding_dimensions=4096,
        )


def test_deepseek_and_siliconflow_fields_have_expected_defaults():
    """新的提供方字段必须存在，并带有计划里要求的默认值。"""
    settings = Settings(_env_file=None)

    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.siliconflow_base_url == "https://api.siliconflow.cn/v1"
    assert settings.rerank_model == "Qwen/Qwen3-Reranker-8B"



def test_settings_accept_known_legacy_env_fields_without_extra_forbidden():
    """当前旧 .env 中的已知遗留字段不应再因 extra_forbidden 直接崩掉。"""
    settings = Settings(
        _env_file=None,
        llm_api_key="legacy-llm-key",
        embedding_api_key="legacy-embedding-key",
        rerank_base_url="https://legacy.example.com/rerank",
        ocr_api_key="legacy-ocr-key",
        ocr_model="legacy-ocr-model",
    )

    assert settings.deepseek_api_key == "legacy-llm-key"
    assert settings.siliconflow_api_key == "legacy-embedding-key"



def test_settings_can_load_current_env_file_when_embedding_dimension_is_1536():
    """当前 backend/.env 至少要和 1536 维契约一致，避免真实运行路径直接启动失败。"""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    settings = Settings(_env_file=env_file)

    assert settings.embedding_dimensions == 1536
    assert settings.embedding_dimension == 1536



def test_local_mvp_defaults_to_loopback_host():
    """本地单机 MVP 默认只应监听本机，避免无鉴权接口暴露到局域网。"""
    settings = Settings(_env_file=None)
    assert settings.app_host == "127.0.0.1"
