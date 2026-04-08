"""Pytest 配置."""
import pytest


def pytest_configure(config):
    """Pytest 配置钩子."""
    config.addinivalue_line(
        "markers",
        "unit: 单元测试（不依赖外部服务）",
    )
    config.addinivalue_line(
        "markers",
        "integration: 集成测试（依赖外部服务）",
    )
    config.addinivalue_line(
        "markers",
        "slow: 慢速测试（运行时间较长）",
    )
