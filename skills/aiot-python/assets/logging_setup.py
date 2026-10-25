"""
logging 設定範本

用法：程式進入點 (main.py) 最前面呼叫一次 setup_logging()，其他模組只寫
    logger = logging.getLogger(__name__)

環境變數：
    LOG_LEVEL        應用程式 log 等級 (DEBUG / INFO / WARNING / ERROR)，預設 INFO
    LOG_FILE         log 檔路徑，空字串表示不寫檔，預設 logs/app.log
    LOG_BACKUP_DAYS  log 檔保留天數，預設 14
"""

import contextvars
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# 目前請求的 request_id，由 errors.py 的 middleware 設定，沒有請求時為 "-"
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s:%(lineno)d] [%(request_id)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 第三方套件只顯示 WARNING 以上，避免洗版
NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "paho", "asyncio", "multipart", "google_genai", "openai")

COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;37;41m",
}
RESET = "\033[0m"


class RequestIdFilter(logging.Filter):
    """把 request_id 塞進每筆 log record，格式字串才能用 %(request_id)s"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class ColorFormatter(logging.Formatter):
    """終端機依等級上色；寫檔的 handler 不要用"""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = COLORS.get(record.levelno)
        return f"{color}{message}{RESET}" if color else message


def _parse_level(name: str) -> int | None:
    level = logging.getLevelName(name.upper())
    return level if isinstance(level, int) else None


def setup_logging() -> None:
    """設定 root logger：終端輸出 + 每天輪替的 log 檔。重複呼叫會先清掉舊的 handler"""
    level_name = os.getenv("LOG_LEVEL", "INFO")
    level = _parse_level(level_name)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level if level is not None else logging.INFO)

    request_id_filter = RequestIdFilter()

    # Windows 下 stderr 被導向檔案 / docker logs 時預設是 cp950，中文會變亂碼
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    console = logging.StreamHandler(sys.stderr)
    use_color = sys.stderr.isatty() and os.getenv("NO_COLOR") is None
    console.setFormatter(
        ColorFormatter(LOG_FORMAT, DATE_FORMAT) if use_color else logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )
    console.addFilter(request_id_filter)
    root.addHandler(console)

    log_file = os.getenv("LOG_FILE", "logs/app.log")
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            path,
            when="midnight",
            backupCount=int(os.getenv("LOG_BACKUP_DAYS", "14")),
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        file_handler.addFilter(request_id_filter)
        root.addHandler(file_handler)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn 請用 uvicorn.run(..., log_config=None) 啟動，讓它的 log 走上面這組 handler
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    if level is None:
        logging.getLogger(__name__).warning("LOG_LEVEL=%s 不是合法的等級，改用 INFO", level_name)
