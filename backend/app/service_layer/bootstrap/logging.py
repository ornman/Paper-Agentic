from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 事件前缀模式：import.* / agent.* / compact.* / runtime.*
_EVENT_PATTERN = re.compile(r"^(import|agent|compact|runtime)\.\S+")

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_LOG_DIR = _BACKEND_ROOT.parent / "log"


class JSONFormatter(logging.Formatter):
    """结构化 JSON Lines 格式化器。

    每条日志输出一行 JSON，至少包含 timestamp / level / event / logger 四个字段。
    如果日志消息以 agent.*/compact.*/import.*/runtime. 开头，自动提取为 event 字段。
    """

    def format(self, record: logging.LogRecord) -> str:
        event = record.getMessage()
        match = _EVENT_PATTERN.match(event)
        if match:
            event = match.group(0)

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": event,
            "logger": record.name,
        }

        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    formatter = JSONFormatter()

    # stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    root = logging.getLogger("paper-assistant")
    root.setLevel(logging.INFO)
    root.addHandler(stdout_handler)
    root.propagate = False

    # file handler — 写入项目根目录 log/app.log
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            _LOG_DIR / "app.log", encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # 日志目录不可写时不影响启动
        pass
