---
name: aiot-python
description: "Python coding standard for AIoT / Web backends (FastAPI, MQTT, LLM agents, device scripts). Use whenever writing, modifying or reviewing Python code - new API endpoints, services, MQTT clients, background workers, scripts - to enforce logging (no print), try-except rules, typed config, layered controller/service/dto structure, and REST API conventions (status codes, error format, naming, pagination). Triggers on Chinese: 寫 python / 新增 API / 寫 endpoint / 加 log / 錯誤處理 / try except / 例外處理 / FastAPI / MQTT client / 重構 python / code review python. Do not trigger for non-Python code."
version: 1.0.0
---

# AIoT / Web Python 開發規範

寫或改任何 Python 程式碼時套用本規範。目標：**出事時看 log 就知道哪裡壞、為什麼壞；API 的使用者不用猜回傳格式；錯誤不會被默默吞掉。**

依據：Python 官方 Logging HOWTO、PEP 8、RFC 9457（Problem Details for HTTP APIs）、Zalando RESTful API Guidelines、Microsoft REST API Guidelines、FastAPI 官方文件。

---

## 0. 觸發後第一件事

1. **先看專案現況，現有慣例優先**：讀 `CLAUDE.md` / `AGENTS.md`、`pyproject.toml`、`ruff.toml`、`mypy.ini`，找專案已經有的 logger 模組（例如 `utils/logging_colors.py`、`loggers.py`）、設定模組、錯誤回傳格式。**已經有的就沿用，不要再造一套**
2. 依任務讀對應 reference：

| 任務 | 讀 |
|---|---|
| 加 log、設定 logging、log 太多 / 太少 | `references/logging.md` |
| try-except、錯誤處理、重試、逾時、背景任務 | `references/exceptions.md` |
| 新增 / 修改 API endpoint、錯誤回傳格式、命名、分頁 | `references/api-design.md` |
| 新專案、缺 logger / 錯誤處理骨架 | 複製 `assets/` 的範本（§6） |

---

## 1. 紅線

1. **不用 `print()` 當 log**。CLI 給人看的輸出才用 `print`，其餘一律 `logger`
2. **不准吞例外**：`except: pass`、`except Exception: pass`、`except Exception: return None` 而沒有 log，一律禁止
3. **不准 bare `except:`**（會連 `KeyboardInterrupt`、`SystemExit` 一起吃掉）
4. **不准把機密寫進程式碼或 log**：密碼、token、API key、完整的 Authorization header、`.env` 內容、個資（身分證、病歷、完整電話）。設定從環境變數讀
5. **不准把 traceback 或內部錯誤訊息回給 API 使用者**：`str(e)`、SQL 錯誤、檔案路徑只進 log，回應只給可理解的訊息

---

## 2. Logging（細節見 `references/logging.md`）

```python
import logging

logger = logging.getLogger(__name__)   # 每個模組一行，放在 import 下面
```

- logging 只在程式進入點（`main.py`）設定一次；其他模組只 `getLogger(__name__)`。專案已有共用 logger（如 `from utils.logging_colors import logger`）就用它
- 等級：`DEBUG` 除錯細節 / `INFO` 正常的重要事件（啟動、連線成功、任務完成）/ `WARNING` 異常但能繼續（重試、降級、用預設值）/ `ERROR` 這件事失敗了 / `CRITICAL` 整個服務撐不下去
- 在 `except` 裡記錄錯誤用 **`logger.exception(...)`**（自動帶 traceback），或 `logger.error(..., exc_info=True)`；不要手動 `traceback.format_exc()`
- 訊息要能 grep、帶上下文（哪個裝置、哪個 session、多少筆）：
  - ✗ `logger.error("error")`
  - ✓ `logger.error("MQTT 發布失敗 topic=%s device_id=%s", topic, device_id)`
- 新程式碼用 `%s` 延遲格式化；專案既有程式碼全是 f-string 的話跟著用，不要混著大改
- 每個請求 / 每則 MQTT 訊息不要都打 `INFO`，量大的放 `DEBUG`
- 正式環境 log 等級由環境變數 `LOG_LEVEL` 控制，log 檔要有輪替（`RotatingFileHandler` / `TimedRotatingFileHandler`）

---

## 3. try-except（細節見 `references/exceptions.md`）

**原則：只抓你知道怎麼處理的例外；不知道怎麼處理就讓它往上丟，由最外層統一處理。**

```python
try:
    payload = json.loads(msg.payload)
except json.JSONDecodeError:
    logger.warning("忽略非 JSON 的 MQTT 訊息 topic=%s", msg.topic)
    return
```

- `try` 區塊越小越好，只包「可能出錯的那一行」
- 抓**具體的**例外（`ValueError`、`KeyError`、`httpx.TimeoutException`、`sqlite3.Error`…），不要一律 `except Exception`
- `except Exception` 只准出現在**邊界**：API 的全域 exception handler、MQTT `on_message` callback、背景任務 / worker 迴圈最外層、`main()`。而且一定要 `logger.exception`
- 抓到後只有三種合法處理：
  1. **處理掉**：有明確的替代行為（用預設值、略過這筆），並 log `WARNING`
  2. **包裝後再丟**：轉成業務例外 `raise DeviceOfflineError(device_id) from e`（保留原因鏈）
  3. **記錄後重新丟**：`logger.exception(...)` 然後 `raise`
- 需要清理資源用 `with` / `finally`，不要靠 except
- 外部 I/O（HTTP、MQTT、DB、序列埠、LLM API）**一定要設 timeout**；重試要有上限和退避
- `asyncio.create_task` / FastAPI `BackgroundTasks` / thread 裡的例外沒人接，函式內部最外層一定要 try + `logger.exception`

---

## 4. API（細節見 `references/api-design.md`）

**分層**（沿用你專案的 controller / service / dto）：

```
controllers/   路由：解析請求、呼叫 service、回傳 response_model。不寫商業邏輯
services/      商業邏輯：拋業務例外，不碰 HTTP（不 import fastapi）
dtos/          Pydantic request / response model
utils/         DB、MQTT、檔案、外部 API 的存取
```

**錯誤回傳格式**（兩種擇一，同一個專案不可混用）：

| | 新專案（業界標準） | 既有專案已在用的「status 碼」格式 |
|---|---|---|
| HTTP 狀態碼 | 照語意：400 / 401 / 403 / 404 / 409 / 422 / 429 / 500 / 503 | 一律 200 |
| body | RFC 9457 problem details：`{"type", "title", "status", "detail", "instance", "code", "request_id"}`，`Content-Type: application/problem+json` | `{"status": "0", "message": "..."}`，`"0"` 成功，其他碼列在 docstring 的 Return Status |
| 未知錯誤 | 500 + 通用訊息 + `request_id`，細節只進 log | `"87"` + 通用訊息，細節只進 log |

**命名**：路徑用複數名詞 + kebab-case（`/api/v1/devices/{device_id}/sensor-readings`），不放動詞；JSON 欄位 snake_case；時間用 ISO 8601 / RFC 3339（`2026-10-25T08:30:00Z`），欄位名 `xxx_at`。

**每個 endpoint 必須**：有 `response_model`、有 docstring 說明輸入 / 輸出 / 所有可能的錯誤、request 用 Pydantic 驗證（範圍、長度、enum）、列表要分頁。

---

## 5. 其他基本規範

- **設定**：用 `pydantic-settings` 或集中在 `config.py`，從環境變數 / `.env` 讀，啟動時就驗證；不要在各處散落 `os.getenv("X", "預設")`
- **型別標註**：所有新函式的參數與回傳值都要標（`def get_device(device_id: str) -> Device:`）；Python 3.10+ 用 `str | None`
- **命名**（PEP 8）：函式 / 變數 `snake_case`、類別 `PascalCase`、常數 `UPPER_SNAKE_CASE`、模組檔名 `snake_case.py`
- **註解**：寫「為什麼」，不寫「做了什麼」；跟著專案語言（中文專案就寫中文）。docstring 用三引號放在函式第一行
- **不要在 import 時做事**：連線 DB / MQTT、讀大檔放到 `lifespan` 或 `main()`，不要寫在模組最上層
- **async**：`async def` 裡不呼叫阻塞函式（`time.sleep`、`requests`、同步 DB、大量 CPU 運算），改用 `asyncio.sleep`、`httpx.AsyncClient`，或 `await asyncio.to_thread(...)`
- **路徑**：用 `pathlib.Path`，不要寫死 `C:\\Users\\...`
- **品質工具**：專案有 ruff / mypy 就在完成前跑；新專案可用 `assets/ruff.toml`（含 `BLE` 盲抓例外、`G` log 格式、`T20` print 檢查）

---

## 6. 新專案骨架（`assets/`）

專案缺少時才複製，已有同功能的模組就不要放：

| 檔案 | 用途 |
|---|---|
| `assets/logging_setup.py` | `setup_logging()`：終端 + 輪替檔案、`LOG_LEVEL`、壓低第三方套件、request_id 欄位 |
| `assets/errors.py` | `AppError` 業務例外階層 + FastAPI 全域 exception handler（RFC 9457 格式）+ request_id middleware |
| `assets/ruff.toml` | 建議的 ruff 規則 |
| `examples/device_api.py` | controller / service / dto 一條龍範例（含 log、例外、分頁） |

---

## 7. 完成前自我檢查

寫完 / 改完 Python 程式碼，回報前逐條確認：

- [ ] 沒有新增 `print()`（CLI 輸出除外）
- [ ] 每個 `except` 都是具體例外，或位於邊界且有 `logger.exception`
- [ ] 沒有 `except: pass`、沒有吞掉例外
- [ ] 外部 I/O 都有 timeout
- [ ] log 有上下文、沒有機密 / 個資
- [ ] API 錯誤回應沒有 traceback / `str(e)`，格式跟專案其他 endpoint 一致
- [ ] 新 endpoint 有 `response_model`、docstring、輸入驗證
- [ ] 新函式有型別標註
- [ ] 專案有設定的 ruff / mypy / pytest 跑過，結果如實回報
