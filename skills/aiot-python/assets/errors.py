"""
業務例外 + FastAPI 全域錯誤處理範本 (RFC 9457 Problem Details)

用法：
    from errors import NotFoundError, register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    # service 層
    raise NotFoundError(f"找不到裝置 {device_id}", code="DEVICE_NOT_FOUND")

所有錯誤回應都是 application/problem+json：
    {"type", "title", "status", "detail", "instance", "code", "request_id", "errors"?}

依賴 logging_setup.py 的 request_id_var (放在同一個套件，或依專案調整 import 路徑)。
"""

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from logging_setup import request_id_var
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"
REQUEST_ID_HEADER = "X-Request-ID"


# ---------- 業務例外 ----------


class AppError(Exception):
    """所有業務例外的基底。service 層丟這些，不要丟 HTTPException"""

    status_code = 500
    code = "INTERNAL_ERROR"
    title = "伺服器內部錯誤"

    def __init__(self, detail: str | None = None, *, code: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        if code:
            self.code = code
        # 額外想回給呼叫端的欄位，例如 retry_after_sec
        self.extra = extra


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"
    title = "請求格式錯誤"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    title = "未授權"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    title = "沒有權限"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    title = "找不到資源"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    title = "狀態衝突"


class ValidationFailedError(AppError):
    status_code = 422
    code = "VALIDATION_FAILED"
    title = "欄位驗證失敗"


class ExternalServiceError(AppError):
    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
    title = "上游服務錯誤"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    title = "服務暫時無法使用"


class ServiceTimeoutError(AppError):
    status_code = 504
    code = "UPSTREAM_TIMEOUT"
    title = "上游服務逾時"


# ---------- 回應 model (給 OpenAPI 文件用：responses={404: {"model": Problem}}) ----------


class FieldError(BaseModel):
    field: str
    message: str


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: list[FieldError] | None = None


def _problem(request: Request, status: int, title: str, detail: str, code: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": request_id_var.get(),
        **extra,
    }
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE)


# ---------- handlers ----------


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    # AppError 是預期中、已處理的錯誤 (含裝置離線、上游逾時)，記 WARNING；
    # 有原因鏈 (raise ... from e) 時附上 traceback 方便追查。真正未預期的錯誤走 _handle_unexpected 記 ERROR
    logger.warning(
        "%s %s -> %s %s: %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.code,
        exc.detail,
        exc_info=exc.__cause__ is not None,
    )
    return _problem(request, exc.status_code, exc.title, exc.detail, exc.code, **exc.extra)


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail if isinstance(exc.detail, str) else "請求失敗"
    response = _problem(request, exc.status_code, detail, detail, f"HTTP_{exc.status_code}")
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # 不直接回 str(exc)，會帶出內部資訊；一次整理出所有欄位錯誤
    errors = [
        {"field": ".".join(str(part) for part in err["loc"] if part != "body"), "message": err["msg"]}
        for err in exc.errors()
    ]
    logger.info("%s %s -> 422 欄位驗證失敗 %s", request.method, request.url.path, errors)
    return _problem(request, 422, "欄位驗證失敗", "請求欄位不符合格式", "VALIDATION_FAILED", errors=errors)


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    # 真正原因只進 log，回應只給通用訊息與 request_id
    logger.error("%s %s -> 500 未預期錯誤", request.method, request.url.path, exc_info=exc)
    return _problem(request, 500, "伺服器內部錯誤", "伺服器發生錯誤，請稍後再試", "INTERNAL_ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    """註冊全域錯誤處理與 request_id / 存取 log middleware"""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:  # noqa: BLE001 - 邊界：所有未預期例外在這裡統一處理
                # 在這裡接住未預期例外，回應與 log 才帶得到 request_id
                response = await _handle_unexpected(request, exc)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
            return response
        finally:
            request_id_var.reset(token)
