# 启动入口
import uvicorn
from app.core.config import get_settings
from app.core.logging_config import initialize_log_cleanup


if __name__ == "__main__":
    # 🔴 P1-4 优化：应用启动时清理过期日志
    initialize_log_cleanup()

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
