# API 設計規範

依據：[RFC 9457 Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)、[Zalando RESTful API Guidelines](https://opensource.zalando.com/restful-api-guidelines/)、[Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines)、[FastAPI Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)、RFC 9110（HTTP Semantics）、RFC 3339（日期時間）。

**既有專案的慣例優先於本文件**。專案已經有自己的路徑風格、回傳格式、狀態碼表，新 endpoint 跟著用；本文件用在新專案，或專案還沒有慣例的部分。

---

## 1. 分層

```
controllers/xxx_controller.py   APIRouter；解析請求 → 呼叫 service → 回傳 response_model
services/xxx_service.py         商業邏輯；拋 AppError 子類別；不 import fastapi
dtos/xxx/                       Pydantic request / response model
utils/ 或 repositories/         DB、MQTT、檔案、外部 API 的存取
```

- controller 不寫商業邏輯、不直接碰 DB
- service 不回傳 `JSONResponse`、不丟 `HTTPException`（這樣 service 也能給 MQTT handler、CLI、測試重用）
- 完整範例：`examples/device_api.py`

---

## 2. URL

| 規則 | ✓ | ✗ |
|---|---|---|
| 資源用複數名詞 | `/devices` | `/device`、`/getDevices` |
| 不放動詞，動作靠 HTTP method | `POST /devices` | `/devices/create` |
| path 用 kebab-case | `/sensor-readings` | `/sensorReadings`、`/sensor_readings` |
| 子資源表達從屬 | `/devices/{device_id}/readings` | `/readings?device=...`（當它確實從屬時） |
| 不加結尾斜線 | `/devices` | `/devices/` |
| 版本放路徑前綴（內部 / App 用 API 最簡單的做法） | `/api/v1/devices` | — |

真的不是 CRUD 的動作（開冷氣、重新開機、觸發辨識），用子資源表示動作：`POST /devices/{device_id}/commands`（body：`{"command": "power_on"}`）或 `POST /devices/{device_id}/reboot`。團隊統一一種。

> 版本：Zalando 主張避免 URL 版本、改用 media type；Microsoft、Google 與多數內部 API 用路徑版本。App / IoT 裝置對接以簡單為主，採 `/api/v1`。有不相容變更才升 `v2`，舊版保留到所有 client 更新完。

---

## 3. HTTP method

| method | 用途 | 成功回應 | 冪等 |
|---|---|---|---|
| `GET` | 讀取，**不可有副作用** | 200 | 是 |
| `POST` | 新增、觸發動作 | 201（新增，附 `Location` header）/ 200 / 202（非同步受理） | 否 |
| `PUT` | 整筆取代 | 200 / 204 | 是 |
| `PATCH` | 部分更新 | 200 | 否 |
| `DELETE` | 刪除 | 204 | 是 |

裝置指令這類「重送會出事」的 POST（重複開關、重複扣款），可接受 `Idempotency-Key` header 去重。

---

## 4. JSON 欄位

- **snake_case**：`device_id`、`created_at`（跟 Python 一致，Pydantic 不用 alias）
- 時間：ISO 8601 / RFC 3339 字串，UTC 加 `Z` 或帶時區 `+08:00`；欄位名 `xxx_at`（時間點）、`xxx_date`（日期）。裝置端只能送 epoch 時，欄位名寫明單位：`timestamp_ms`
- 數值帶單位時欄位名寫單位：`temperature_c`、`duration_sec`、`size_bytes`
- 列表欄位用複數：`devices`、`images`；空列表回 `[]`，不要回 `null`
- enum 用固定字串（`"cool"` / `"heat"` / `"fan"`），在 Pydantic 用 `Literal` 或 `Enum` 限定
- 布林不要用 `null` 表示第三種狀態
- 不要把整包 dict 不經 model 直接回傳；一律經 `response_model`，避免多回內部欄位

---

## 5. 狀態碼（新專案）

用**最貼切**的狀態碼，不要全部回 200 或 500：

| 碼 | 什麼時候 |
|---|---|
| 200 OK | 成功並回傳內容 |
| 201 Created | 新增成功 |
| 202 Accepted | 已受理、背景處理中（長時間的 LLM / 影像辨識任務） |
| 204 No Content | 成功、沒有內容（DELETE） |
| 400 Bad Request | 請求格式錯誤（不是 JSON、base64 解不開） |
| 401 Unauthorized | 沒帶或帶錯憑證 |
| 403 Forbidden | 有登入但沒權限 |
| 404 Not Found | 資源不存在 |
| 409 Conflict | 狀態衝突（重複建立、session 已結束） |
| 413 Content Too Large | 上傳檔案太大 |
| 415 Unsupported Media Type | 檔案格式不支援 |
| 422 Unprocessable Content | 欄位驗證失敗（FastAPI 預設） |
| 429 Too Many Requests | 限流，附 `Retry-After` |
| 500 Internal Server Error | 未預期錯誤 |
| 502 Bad Gateway | 上游（LLM、第三方 API）回錯誤 |
| 503 Service Unavailable | 服務 / 裝置暫時不可用（裝置離線、broker 斷線） |
| 504 Gateway Timeout | 上游逾時 |

---

## 6. 錯誤回應格式

### 6.1 新專案：RFC 9457 Problem Details

`Content-Type: application/problem+json`

```json
{
  "type": "about:blank",
  "title": "找不到資源",
  "status": 404,
  "detail": "找不到裝置 ac-livingroom",
  "instance": "/api/v1/devices/ac-livingroom",
  "code": "DEVICE_NOT_FOUND",
  "request_id": "6f1c2a9e0b7d4c1e"
}
```

| 欄位 | 說明 |
|---|---|
| `type` | 問題類型 URI；沒有文件頁就用 `about:blank` |
| `title` | 該類問題的固定簡述（同一類每次一樣） |
| `status` | 跟 HTTP 狀態碼相同 |
| `detail` | 這一次的具體說明，給人看、幫助呼叫端修正，**不放 debug 資訊** |
| `instance` | 這次請求的路徑 |
| `code`（擴充） | 機器判斷用的錯誤碼，UPPER_SNAKE_CASE，前端 / App 依它分支 |
| `request_id`（擴充） | 對應 log 的追蹤 ID，回報問題時用 |
| `errors`（擴充，驗證錯誤時） | `[{"field": "temperature_c", "message": "必須介於 16 到 30"}]`，一次回全部錯誤 |

未知錯誤（500）：`detail` 固定寫「伺服器發生錯誤，請稍後再試」，加 `request_id`；真正原因只在 log。**絕不回 traceback、`str(e)`、SQL、檔案路徑**。

實作：`assets/errors.py` 的 `register_exception_handlers(app)`，會統一處理 `AppError`、`HTTPException`、`RequestValidationError`、未知例外。

### 6.2 既有專案：一律 200 + status 碼

專案已經是這種格式（如 AI_Next_Wearable 的 `BaseResponse(status="0", message="")`）時，**繼續沿用**，App 端已經依它寫好判斷：

- 所有 response model 繼承專案的 `BaseResponse`
- 狀態碼表集中定義（常數或 Enum），不要散落魔術字串；新增碼要更新 docstring 的 Return Status
- 每支 endpoint 的 docstring 列出 Input Request、Response、Return Status 全部可能值
- 未知錯誤回專案約定的碼（如 `"87"`）+ 通用 `message`，細節 `logger.exception` 進 log
- `message` 給人看，不放 `str(e)`

---

## 7. 列表與分頁

列表 endpoint 一定要分頁，不要一次回全部：

```
GET /api/v1/devices/{device_id}/readings?limit=50&cursor=eyJpZCI6MTIzfQ
```

```json
{
  "items": [ ... ],
  "next_cursor": "eyJpZCI6MTczfQ",
  "has_more": true
}
```

- 資料會持續增加（感測紀錄、log、事件）→ **cursor 分頁**（用最後一筆的 id / 時間編碼），新資料插入不會跳號重複
- 小量、固定的資料、需要跳頁 → `offset` + `limit` 可接受
- `limit` 設預設值（例如 50）和上限（例如 200），用 `Query(50, ge=1, le=200)` 驗證
- 篩選 / 排序用 query：`?status=online&sort=-created_at`

---

## 8. 輸入驗證

- request 一律用 Pydantic model，不要手動 `request.json()` 再 `dict["x"]`
- 範圍、長度、格式寫在 model：`Field(ge=16, le=30)`、`Field(max_length=64)`、`Literal["cool", "heat"]`
- base64 檔案先檢查大小上限再解碼
- 不信任 client 給的任何值（路徑、檔名 → 防 path traversal；SQL → 一律參數化查詢）

---

## 9. 文件

- 每支 endpoint：`response_model`、`summary` / docstring（做什麼、輸入、輸出、可能的錯誤）、`tags`
- 可能的錯誤用 `responses={404: {"model": Problem}, ...}` 標出，會顯示在 `/docs`
- 不相容的變更（改欄位名、改型別、刪欄位、改路徑）= Breaking change：升版或先並存舊欄位，commit 寫 `Breaking:`（見 `aiot-git-workflow`）

---

## 10. 安全與營運

- CORS：正式環境列出允許的來源，不要 `allow_origins=["*"]` 搭配 `allow_credentials=True`
- 需要驗證的 API 用 `Depends` 統一檢查（API key header / JWT），不要每支自己寫
- 每個請求產生 `request_id`（或沿用 client 送來的 `X-Request-ID`），寫進 log 並回在 response header 與錯誤 body
- 提供 `GET /health`（存活）讓 Docker / 監控用，不需驗證、不碰外部服務；需要檢查相依服務的另開 `/health/ready`
- 上傳大小、請求頻率要有上限
