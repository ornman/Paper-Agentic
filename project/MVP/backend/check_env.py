#!/usr/bin/env python3
"""
环境检查脚本
检查 Python 版本、依赖、API Keys 等环境配置
"""

import os
import sys
from pathlib import Path


def check_python_version():
    """检查 Python 版本."""
    print("[1/6] 检查 Python 版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 12):
        print(f"❌ Python 版本过低: {sys.version}")
        print("   需要 Python 3.12 或更高版本（推荐 3.13）")
        return False

    if version.minor == 12:
        print(f"⚠️  Python 版本: {sys.version.split()[0]} (推荐 3.13)")
    else:
        print(f"✅ Python 版本: {sys.version.split()[0]}")
    return True


def check_uv():
    """检查 uv 包管理器."""
    print("[2/6] 检查 uv 包管理器...")
    try:
        import subprocess
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"✅ uv 版本: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  uv 未安装")
        print("   安装命令: pip install uv")
        return False


def check_dependencies():
    """检查项目依赖."""
    print("[3/6] 检查项目依赖...")
    if not Path("pyproject.toml").exists():
        print("❌ 未找到 pyproject.toml")
        return False

    print("✅ 找到 pyproject.toml")
    return True


def check_env_file():
    """检查环境变量文件."""
    print("[4/6] 检查环境变量...")

    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  未找到 .env 文件")
        print("   正在创建示例配置...")

        example_env = """# Kimi Coding API（VLM + LLM）
KIMI_API_KEY=your_kimi_api_key
KIMI_BASE_URL=https://api.kimi.com/coding/v1

# 硅基流动（Embedding + Rerank）
SILICONFLOW_API_KEY=your_siliconflow_api_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# DeepSeek（主问答）
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 固定模型契约（不可更改）
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_DIMENSIONS=1536
RERANK_MODEL=Qwen/Qwen3-Reranker-8B
"""

        env_file.write_text(example_env, encoding="utf-8")
        print("✅ 已创建 .env 示例文件")
        print("   ⚠️  请编辑 .env 文件，填入真实的 API Keys")
        return False

    print("✅ 找到 .env 文件")

    # 检查关键环境变量
    required_keys = [
        "KIMI_API_KEY",
        "SILICONFLOW_API_KEY",
        "DEEPSEEK_API_KEY",
    ]

    missing_keys = []
    env_content = env_file.read_text(encoding="utf-8")

    for key in required_keys:
        if f"{key}=" in env_content and f"{key}=your_" in env_content:
            missing_keys.append(key)

    if missing_keys:
        print(f"⚠️  以下 API Keys 需要配置: {', '.join(missing_keys)}")
        print("   请在 .env 文件中填入真实的 API Keys")
        return False

    print("✅ 环境变量配置完整")
    return True


def check_data_directories():
    """检查数据目录."""
    print("[5/6] 检查数据目录...")

    required_dirs = [
        "data/qdrant",
        "data/papers",
        "data/uploads",
    ]

    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    print("✅ 数据目录已就绪")
    return True


def check_port_availability():
    """检查端口可用性."""
    print("[6/6] 检查端口可用性...")

    import socket

    port = 8000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        print(f"✅ 端口 {port} 可用")
        return True
    except OSError:
        print(f"⚠️  端口 {port} 已被占用")
        print("   请检查是否有其他服务正在使用该端口")
        return False
    finally:
        sock.close()


def main():
    """主函数."""
    print("=" * 40)
    print("论文助手 - 环境检查")
    print("=" * 40)
    print()

    checks = [
        check_python_version(),
        check_uv(),
        check_dependencies(),
        check_env_file(),
        check_data_directories(),
        check_port_availability(),
    ]

    print()
    print("=" * 40)

    if all(checks):
        print("✅ 环境检查通过！")
        print()
        print("启动命令:")
        print("  Windows: start.bat")
        print("  Linux/Mac: ./start.sh")
        print("  Docker: docker-compose up")
        return 0
    else:
        print("❌ 环境检查失败，请修复上述问题后重试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
