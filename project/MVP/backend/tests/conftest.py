# pytest 全局测试夹具
# 这里统一处理导入路径与配置缓存，避免不同测试之间共享旧状态
import sys
from pathlib import Path

import pytest

# 将 backend 根目录加入导入路径，确保测试可直接导入 app 包
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings

# 这些环境变量会直接影响 Settings 的默认值测试。
# 测试环境必须先清空它们，避免宿主机器或 CI 的环境污染测试结果。
SETTINGS_ENV_KEYS = [
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "SILICONFLOW_API_KEY",
    "SILICONFLOW_BASE_URL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "RERANK_API_KEY",
    "RERANK_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_DIMENSION",
]


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch):
    """每个测试前先清空关键配置环境变量，避免默认值断言被宿主环境污染。"""
    for key in SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """每个测试前后都清理配置缓存，确保环境变量修改即时生效。"""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
