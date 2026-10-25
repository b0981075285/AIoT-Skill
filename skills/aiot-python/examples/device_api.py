"""
controller / service / dto 一條龍範例：查詢裝置、讀取感測紀錄 (cursor 分頁)、送冷氣指令

實際專案拆成多個檔案：
    dtos/device/device_payload.py        -> 「DTO」區塊
    services/device_service.py           -> 「Service」區塊
    controllers/device_controller.py     -> 「Controller」區塊
    main.py                              -> 「進入點」區塊

搭配 assets/logging_setup.py 與 assets/errors.py：
    uv run uvicorn device_api:app --reload
"""

import asyncio
import base64
import binascii
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

import uvicorn
from errors import (
    BadRequestError,
    NotFoundError,
    Problem,
    ServiceTimeoutError,
    ServiceUnavailableError,
    register_exception_handlers,
)
from fastapi import APIRouter, FastAPI, Query, status
from logging_setup import setup_logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ======================== DTO ========================


class Device(BaseModel):
    device_id: str
    name: str
    is_online: bool
    last_seen_at: datetime


class SensorReading(BaseModel):
    reading_id: int
    temperature_c: float
    humidity_percent: float
    measured_at: datetime


class SensorReadingPage(BaseModel):
    items: list[SensorReading]
    next_cursor: str | None
    has_more: bool


class AcCommandRequest(BaseModel):
    power: Literal["on", "off"]
    mode: Literal["cool", "heat", "fan", "dry"] = "cool"
    temperature_c: int = Field(26, ge=16, le=30, description="設定溫度，16 到 30 度")


class AcCommandResponse(BaseModel):
    device_id: str
    accepted_at: datetime


# ======================== Service ========================

# 示範用的假資料；實際從 DB 讀
_DEVICES = {
    "ac-livingroom": Device(
        device_id="ac-livingroom", name="客廳冷氣", is_online=True, last_seen_at=datetime.now(timezone.utc)
    ),
    "ac-bedroom": Device(
        device_id="ac-bedroom",
        name="臥室冷氣",
        is_online=False,
        last_seen_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    ),
}
_READINGS = [
    SensorReading(reading_id=i, temperature_c=25 + i % 5, humidity_percent=60, measured_at=datetime.now(timezone.utc))
    for i in range(1, 121)
]

MQTT_PUBLISH_TIMEOUT_SEC = 5


def _encode_cursor(reading_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"id": reading_id}).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(json.loads(base64.urlsafe_b64decode(cursor.encode()))["id"])
    except (binascii.Error, ValueError, KeyError, TypeError) as e:
        # 包裝成業務例外，保留原因鏈；呼叫端拿到 400
        raise BadRequestError("cursor 格式錯誤", code="INVALID_CURSOR") from e


async def _mqtt_publish(topic: str, payload: dict) -> None:
    """示範用；實際呼叫 MQTT client，並設 timeout"""
    await asyncio.sleep(0.01)


class DeviceService:
    """商業邏輯：只丟 AppError 子類別，不 import fastapi 的 HTTP 相關東西"""

    @staticmethod
    def get_device(device_id: str) -> Device:
        device = _DEVICES.get(device_id)
        if device is None:
            raise NotFoundError(f"找不到裝置 {device_id}", code="DEVICE_NOT_FOUND")
        return device

    @staticmethod
    def list_readings(device_id: str, limit: int, cursor: str | None) -> SensorReadingPage:
        DeviceService.get_device(device_id)
        after_id = _decode_cursor(cursor) if cursor else 0

        rows = [r for r in _READINGS if r.reading_id > after_id][: limit + 1]
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = _encode_cursor(items[-1].reading_id) if has_more else None

        logger.debug("讀取感測紀錄 device_id=%s after_id=%s count=%d", device_id, after_id, len(items))
        return SensorReadingPage(items=items, next_cursor=next_cursor, has_more=has_more)

    @staticmethod
    async def send_ac_command(device_id: str, command: AcCommandRequest) -> AcCommandResponse:
        device = DeviceService.get_device(device_id)
        if not device.is_online:
            # 裝置離線是常態，不是程式錯誤：回 503，由全域 handler 記 WARNING (這裡不重複記)
            raise ServiceUnavailableError(f"裝置 {device_id} 目前離線", code="DEVICE_OFFLINE")

        topic = f"home/ac/{device_id}/set"
        try:
            await asyncio.wait_for(_mqtt_publish(topic, command.model_dump()), timeout=MQTT_PUBLISH_TIMEOUT_SEC)
        except TimeoutError as e:
            raise ServiceTimeoutError("送出指令逾時，請稍後再試", code="MQTT_PUBLISH_TIMEOUT") from e

        logger.info(
            "已送出冷氣指令 device_id=%s power=%s mode=%s temp=%s",
            device_id,
            command.power,
            command.mode,
            command.temperature_c,
        )
        return AcCommandResponse(device_id=device_id, accepted_at=datetime.now(timezone.utc))


# ======================== Controller ========================

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"])

# 每支 endpoint 可能的錯誤，顯示在 /docs
NOT_FOUND = {404: {"model": Problem, "description": "找不到裝置"}}


@router.get("/{device_id}", response_model=Device, responses=NOT_FOUND)
async def get_device(device_id: str) -> Device:
    """查詢單一裝置的狀態"""
    return DeviceService.get_device(device_id)


@router.get("/{device_id}/readings", response_model=SensorReadingPage, responses={**NOT_FOUND, 400: {"model": Problem}})
async def list_readings(
    device_id: str,
    limit: int = Query(50, ge=1, le=200, description="每頁筆數"),
    cursor: str | None = Query(None, description="上一頁回傳的 next_cursor"),
) -> SensorReadingPage:
    """依時間順序列出感測紀錄，cursor 分頁"""
    return DeviceService.list_readings(device_id, limit, cursor)


@router.post(
    "/{device_id}/ac-commands",
    response_model=AcCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **NOT_FOUND,
        503: {"model": Problem, "description": "裝置離線"},
        504: {"model": Problem, "description": "送出逾時"},
    },
)
async def send_ac_command(device_id: str, command: AcCommandRequest) -> AcCommandResponse:
    """送出冷氣指令 (開關、模式、溫度)。指令經 MQTT 送出即回 202，不等裝置執行完"""
    return await DeviceService.send_ac_command(device_id, command)


# ======================== 進入點 ========================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 連線 DB / MQTT 放這裡，不要寫在模組最上層
    logger.info("服務啟動")
    yield
    logger.info("服務關閉")


setup_logging()
app = FastAPI(title="Device API", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(router)


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
