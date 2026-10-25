# Logging 規範

依據：[Python Logging HOWTO](https://docs.python.org/3/howto/logging.html)。

---

## 1. 取得 logger

```python
import logging

logger = logging.getLogger(__name__)
```

- 每個模組一行，logger 名稱跟著模組路徑（`services.device_service`），看 log 就知道從哪來
- **只有程式進入點設定 logging**（`main.py` 呼叫一次 `setup_logging()`）。其他模組不加 handler、不呼叫 `basicConfig`
- 寫成給別人 import 的套件（library）時：只 `getLogger(__name__)`，頂層加 `logging.NullHandler()`，不設定 handler
- 專案已有共用 logger（`from utils.logging_colors import logger`、`loggers.setup_package_logger(...)`）→ 沿用

---

## 2. 等級怎麼選

| 等級 | 什麼時候 | 例子 |
|---|---|---|
| `DEBUG` | 只有除錯時才想看的細節，量大 | 收到的 MQTT payload、LLM prompt、SQL 參數 |
| `INFO` | 正常運作的重要里程碑 | 服務啟動 / 關閉、連上 broker、排程完成、建立 session |
| `WARNING` | 不正常但程式能繼續 | 重試中、用預設值、裝置回應慢、收到格式錯誤的訊息被略過 |
| `ERROR` | 這件事失敗了，需要有人看 | 寫 DB 失敗、呼叫外部 API 重試用盡、未知例外 |
| `CRITICAL` | 整個服務無法運作 | 設定缺失啟動不了、DB 無法連線 |

判斷：「凌晨三點看到這行要不要起床？」要 → `ERROR` 以上；不用但隔天要知道 → `WARNING`。

正式環境預設 `INFO`，第三方套件（`httpx`、`urllib3`、`paho`、`google-genai`、`openai`）壓到 `WARNING`。

---

## 3. 記錄例外

```python
try:
    await save_record(record)
except sqlite3.Error:
    logger.exception("寫入紀錄失敗 session_id=%s", session_id)   # 自動附 traceback，等級 ERROR
    raise
```

- 在 `except` 區塊裡用 `logger.exception(...)`；想用別的等級用 `logger.warning(..., exc_info=True)`
- **不要**：`logger.error(f"失敗 {e}")` 後面再 `logger.debug(traceback.format_exc())`——平常 DEBUG 關著就看不到 traceback 了
- 同一個例外**只記一次**：底層 log 了又 raise，上層又 log，會出現好幾份一樣的 traceback。原則是「誰處理掉，誰記錄」；只是包裝再丟的不用記

---

## 4. 訊息怎麼寫

```python
# ✗
logger.info("done")
logger.error("error")
logger.info(f"user {user} login with password {password}")

# ✓
logger.info("冷氣設定完成 device_id=%s temp=%s mode=%s", device_id, temp, mode)
logger.warning("MQTT 斷線，%s 秒後重連 (第 %d 次)", delay, attempt)
logger.error("Gemini 呼叫逾時 model=%s timeout=%ss", model, timeout)
```

- 帶**識別資訊**（device_id、session_id、request_id、topic、檔名）和**關鍵數值**（筆數、耗時、狀態碼）
- 用 `key=value` 寫法，方便 grep / 之後轉 JSON
- 新程式碼用 `%s` 延遲格式化（log 等級沒開時不會做字串格式化）。既有專案全是 f-string 就跟著用，一致比較重要
- 很貴的參數（大物件序列化）用 `if logger.isEnabledFor(logging.DEBUG):` 包起來
- 長內容截斷：`payload[:200]`；base64 圖片 / 音檔只記長度，不記內容

---

## 5. 不可以記的東西

- 密碼、token、API key、`Authorization` header、cookie、`.env` 內容
- 個資：身分證、病歷內容、完整電話 / 地址、人臉影像
- 完整的 request body（可能夾帶上面的東西）→ 只記需要的欄位

需要對照時記遮罩後的值：`api_key=sk-...{key[-4:]}`。

---

## 6. 該記的地方

| 地方 | 記什麼 |
|---|---|
| 服務啟動 / 關閉 | `INFO`：版本、port、連到哪個 broker / DB（不含密碼） |
| 每個 HTTP 請求 | middleware 統一記 method、path、status、耗時、request_id（`INFO` 或 `DEBUG`），不要每個 endpoint 自己記 |
| 外部呼叫（LLM、第三方 API、MQTT、DB） | 失敗一定記；耗時長的記耗時 |
| 狀態改變 | 裝置上線 / 離線、session 開始 / 結束、排程觸發 |
| 降級 / 走備案 | `WARNING`：為什麼走備案 |
| 例外邊界 | `logger.exception` |

---

## 7. 設定範本

見 `assets/logging_setup.py`：

- 終端輸出（可彩色）+ 檔案輸出（不彩色、`TimedRotatingFileHandler` 每天換檔、保留 N 天、`encoding="utf-8"`）
- `LOG_LEVEL` 環境變數控制應用程式等級，不合法時回退 `INFO`
- 格式：`時間 等級 [logger名稱:行號] [request_id] 訊息`
- uvicorn 用 `log_config=None` 啟動，讓 uvicorn 的 log 走同一組 handler
- Docker / 集中收 log 的環境可改輸出 JSON（`python-json-logger` 或 `structlog`），專案沒用就不要加
