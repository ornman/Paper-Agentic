# 日志系统配置
# 支持自动记录和导出到桌面

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from logging.handlers import RotatingFileHandler

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志级别
LOG_LEVEL = logging.INFO

# 🔴 P1-4 优化：日志轮转配置
MAX_LOG_BYTES = 100 * 1024 * 1024  # 100MB
BACKUP_COUNT = 3  # 保留 3 个备份
LOG_RETENTION_DAYS = 30  # 保留 30 天的日志


class DesktopFileHandler(logging.FileHandler):
    """自定义日志处理器，自动导出到桌面."""

    def __init__(
        self,
        filename: str = "paper_assistant.log",
        mode: str = "a",
        encoding: str | None = "utf-8",
    ) -> None:
        """获取桌面路径并创建日志文件."""
        # 获取桌面路径
        desktop = self._get_desktop_path()
        if desktop:
            log_dir = desktop / "论文助手_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            filepath = log_dir / filename
        else:
            # 降级到当前目录
            filepath = Path("logs") / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

        super().__init__(filepath, mode, encoding)
        self.desktop_path = desktop

    def _get_desktop_path(self) -> Path | None:
        """获取桌面路径."""
        if sys.platform == "win32":
            # Windows
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if os.path.exists(desktop):
                return Path(desktop)
        elif sys.platform == "darwin":
            # macOS
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if os.path.exists(desktop):
                return Path(desktop)
        else:
            # Linux
            # 尝试常见的桌面路径
            desktop_paths = [
                os.path.join(os.path.expanduser("~"), "Desktop"),
                os.path.join(os.path.expanduser("~"), "desktop"),
            ]
            for path in desktop_paths:
                if os.path.exists(path):
                    return Path(path)

        return None


class DateRotatingFileHandler(DesktopFileHandler):
    """按日期轮转的日志处理器."""

    def __init__(
        self,
        filename_prefix: str = "paper_assistant",
        mode: str = "a",
        encoding: str | None = "utf-8",
    ) -> None:
        """使用日期作为文件名."""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{filename_prefix}_{today}.log"
        super().__init__(filename, mode, encoding)
        self.filename_prefix = filename_prefix
        self.current_date = today

    def emit(self, record: logging.LogRecord) -> None:
        """写入日志，检查日期是否变化."""
        # 检查日期是否变化
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.current_date:
            # 关闭当前文件，创建新文件
            if self.stream:
                self.stream.close()
                self.stream = None

            self.current_date = today
            self.baseFilename = str(
                self._get_log_dir() / f"{self.filename_prefix}_{today}.log"
            )
            self.stream = self._open()

        super().emit(record)

    def _get_log_dir(self) -> Path:
        """获取日志目录."""
        desktop = self._get_desktop_path()
        if desktop:
            return desktop / "论文助手_logs"
        else:
            return Path("logs")


# 🔴 P1-4 优化：按大小轮转的日志处理器
class SizeRotatingFileHandler(DesktopFileHandler):
    """按大小轮转的日志处理器（使用 RotatingFileHandler）.

    🔴 P1-4 优化：当日志文件达到 100MB 时轮转，保留 3 个备份
    """

    def __init__(
        self,
        filename: str = "paper_assistant.log",
        mode: str = "a",
        encoding: str | None = "utf-8",
        maxBytes: int = MAX_LOG_BYTES,
        backupCount: int = BACKUP_COUNT,
    ) -> None:
        """初始化大小轮转处理器.

        Args:
            filename: 日志文件名
            mode: 文件模式
            encoding: 文件编码
            maxBytes: 单个日志文件最大字节数
            backupCount: 保留的备份文件数量
        """
        # 获取日志目录
        log_dir = self._get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        filepath = log_dir / filename

        # 使用 RotatingFileHandler
        DesktopFileHandler.__init__(self, str(filepath), mode, encoding)

        # 替换为 RotatingFileHandler
        from logging.handlers import RotatingFileHandler
        self.handler = RotatingFileHandler(
            str(filepath),
            mode=mode,
            encoding=encoding,
            maxBytes=maxBytes,
            backupCount=backupCount,
        )

    def emit(self, record: logging.LogRecord) -> None:
        """写入日志."""
        self.handler.emit(record)

    def close(self) -> None:
        """关闭处理器."""
        self.handler.close()

    def _get_log_dir(self) -> Path:
        """获取日志目录."""
        desktop = self._get_desktop_path()
        if desktop:
            return desktop / "论文助手_logs"
        else:
            return Path("logs")


def setup_logging(
    name: str = "paper_assistant",
    level: int | None = None,
    enable_console: bool = True,
    enable_file: bool = True,
) -> logging.Logger:
    """设置日志系统（支持大小轮转）.

    🔴 P1-4 优化：使用 RotatingFileHandler 实现大小轮转

    Args:
        name: 日志器名称
        level: 日志级别（None 则根据环境自动设置）
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出

    Returns:
        配置好的日志器
    """
    from app.core.config import get_settings

    settings = get_settings()

    # 根据环境自动设置日志级别
    if level is None:
        if settings.is_production:
            level = logging.WARNING
        elif settings.is_staging:
            level = logging.INFO
        else:  # development
            level = logging.DEBUG

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 清除现有处理器
    logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 🔴 P1-4 优化：文件处理器（按大小轮转）
    if enable_file:
        file_handler = SizeRotatingFileHandler()
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # 开发环境显示详细日志
    if settings.is_development:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    return logger


def get_logger(name: str = "paper_assistant") -> logging.Logger:
    """获取日志器实例.

    Args:
        name: 日志器名称

    Returns:
        日志器实例
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 如果没有处理器，自动设置
        return setup_logging(name)
    return logger


def export_logs_to_desktop(
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """导出日志到桌面.

    Args:
        start_date: 开始日期（YYYY-MM-DD），默认今天
        end_date: 结束日期（YYYY-MM-DD），默认今天

    Returns:
        导出的日志文件路径
    """
    logger = get_logger()
    desktop = Path.home() / "Desktop"
    log_dir = desktop / "论文助手_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 确定日期范围
    today = datetime.now().strftime("%Y-%m-%d")
    start = start_date or today
    end = end_date or today

    # 构建导出文件名
    if start == end:
        filename = f"paper_assistant_{start}.log"
    else:
        filename = f"paper_assistant_{start}_to_{end}.log"

    export_path = log_dir / filename

    # 这里可以添加从原始日志文件读取和过滤的逻辑
    # 目前只是创建一个占位文件
    export_path.write_text(
        f"日志导出: {start} 到 {end}\n"
        f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"========================================\n\n"
        f"（日志内容将从原始日志文件中提取）\n",
        encoding="utf-8",
    )

    logger.info(f"日志已导出到: {export_path}")
    return str(export_path)


# 🔴 P1-4 优化：过期日志清理功能
def cleanup_old_logs(days: int = LOG_RETENTION_DAYS) -> int:
    """清理过期的日志文件.

    🔴 P1-4 优化：删除超过指定天数的日志文件

    Args:
        days: 保留天数，默认 30 天

    Returns:
        删除的文件数量
    """
    logger = get_logger()
    desktop = Path.home() / "Desktop"
    log_dir = desktop / "论文助手_logs"

    if not log_dir.exists():
        return 0

    # 计算截止日期
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0

    # 遍历日志文件
    for log_file in log_dir.glob("paper_assistant_*.log"):
        try:
            # 从文件名提取日期
            match = re.search(r'(\d{4}-\d{2}-\d{2})', log_file.name)
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d')
                if file_date < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"删除过期日志: {log_file.name}")
        except Exception as e:
            logger.warning(f"删除日志文件失败 {log_file.name}: {e}")

    if deleted_count > 0:
        logger.info(f"清理完成，删除了 {deleted_count} 个过期日志文件")

    return deleted_count


# 🔴 P1-4 优化：应用启动时清理过期日志
def initialize_log_cleanup():
    """初始化日志清理（应用启动时调用）.

    🔴 P1-4 优化：在应用启动时自动清理过期日志
    """
    try:
        cleanup_old_logs()
    except Exception as e:
        # 清理失败不影响应用启动
        print(f"[LOG] 日志清理失败: {e}")

