@echo off
REM 论文助手一键启动脚本
REM 自动检查环境、安装依赖、启动服务

echo ========================================
echo 论文助手 - 一键启动
echo ========================================
echo.

REM 检查 Python 版本
echo [1/5] 检查 Python 版本...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 未找到 Python
    echo 请安装 Python 3.13 或更高版本
    pause
    exit /b 1
)

python --version
echo ✅ Python 已安装
echo.

REM 检查 uv
echo [2/5] 检查 uv 包管理器...
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  uv 未安装，正在安装...
    pip install uv
    if %errorlevel% neq 0 (
        echo ❌ uv 安装失败
        pause
        exit /b 1
    )
)
uv --version
echo ✅ uv 已就绪
echo.

REM 安装依赖
echo [3/5] 安装项目依赖...
if not exist "pyproject.toml" (
    echo ❌ 错误: 未找到 pyproject.toml
    pause
    exit /b 1
)

uv sync
if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)
echo ✅ 依赖安装完成
echo.

REM 检查环境变量
echo [4/5] 检查环境配置...
if not exist ".env" (
    echo ⚠️  未找到 .env 文件，正在创建示例配置...
    echo KIMI_API_KEY=your_kimi_api_key > .env
    echo SILICONFLOW_API_KEY=your_siliconflow_api_key >> .env
    echo DEEPSEEK_API_KEY=your_deepseek_api_key >> .env
    echo.
    echo ⚠️  请编辑 .env 文件，填入真实的 API Keys
    echo 然后重新运行此脚本
    pause
    exit /b 0
)
echo ✅ 环境配置文件已找到
echo.

REM 启动服务
echo [5/5] 启动服务...
echo ========================================
echo 服务将在 http://localhost:8000 启动
echo API 文档: http://localhost:8000/docs
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

uv run python main.py
