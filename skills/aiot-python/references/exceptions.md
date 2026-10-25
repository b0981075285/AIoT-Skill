# 例外處理（try-except）規範

依據：PEP 8「Programming Recommendations」、Python 官方教學 Errors and Exceptions、FastAPI Handling Errors。

---

## 1. 核心原則

1. **只抓你知道怎麼處理的例外**，其他讓它往上丟
2. **在邊界統一處理未知例外**（API 全域 handler、MQTT callback、worker 迴圈、`main()`）
3. **絕不默默吞掉**：每個被抓住而沒有再丟出的例外都要有 log
4. **保留原因鏈**：包裝成別的例外時用 `raise NewError(...) from e`

---

## 2. 寫法對照

### 2.1 try 範圍最小化

```python
# ✗ 包太多，不知道是哪一行壞，也可能誤抓到 bug
try:
    data = json.loads(raw)
    temp = data["temp"]
    set_ac(device_id, temp)
    save_log(device_id, temp)
except Exception:
    ...

# ✓
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    logger.warning("payload 不是 JSON，略過 device_id=%s", device_id)
    return

temp = data.get("temp")
if temp is None:
    logger.warning("payload 缺少 temp 欄位 device_id=%s", device_id)
    return

set_ac(device_id, temp)
```

能用判斷式避免的就不要靠例外（缺欄位用 `.get()`、檔案先 `Path.exists()` 只在無競爭時適用）。

### 2.2 抓具體例外

| 情境 | 抓 |
|---|---|
| JSON 解析 | `json.JSONDecodeError` |
| 型別 / 數值轉換 | `ValueError`、`TypeError` |
| dict 取值 | `KeyError`（或改用 `.get`） |
| 檔案 | `FileNotFoundError`、`PermissionError`、`OSError` |
| httpx | `httpx.TimeoutException`、`httpx.HTTPStatusError`、`httpx.RequestError` |
| requests | `requests.Timeout`、`requests.ConnectionError`、`requests.HTTPError` |
| SQLite | `sqlite3.IntegrityError`、`sqlite3.OperationalError`、`sqlite3.Error` |
| Pydantic | `pydantic.ValidationError` |
| base64 | `binascii.Error`、`ValueError` |
| asyncio | `asyncio.TimeoutError`（3.11+ 即 `TimeoutError`） |
| 序列埠 | `serial.SerialException` |

### 2.3 三種合法處理

```python
# 1) 處理掉：有明確替代行為
try:
    timeout = float(os.environ["LLM_TIMEOUT"])
except (KeyError, ValueError):
    timeout = 30.0
    logger.warning("LLM_TIMEOUT 未設定或格式錯誤，使用預設 %s 秒", timeout)

# 2) 包裝成業務例外再丟（service 層最常用）
try:
    resp = await client.get(f"/devices/{device_id}", timeout=5)
    resp.raise_for_status()
except httpx.TimeoutException as e:
    raise DeviceTimeoutError(device_id) from e

# 3) 記錄後重新丟（需要在這層補上下文時）
try:
    write_firmware(port, image)
except serial.SerialException:
    logger.exception("燒錄失敗 port=%s", port)
    raise
```

### 2.4 禁止的寫法

```python
except:                          # bare except，連 Ctrl+C 都吃掉
    pass

except Exception:                # 吞掉，沒人知道壞了
    pass

except Exception as e:
    return None                  # 呼叫端只拿到 None，不知道為什麼

except Exception as e:
    raise Exception("失敗")       # 丟掉原因鏈和原始型別

except Exception as e:
    return {"message": str(e)}   # 把內部錯誤（路徑、SQL）回給使用者
```

### 2.5 清理資源用 with / finally

```python
with sqlite3.connect(db_path) as conn:
    ...

lock.acquire()
try:
    ...
finally:
    lock.release()
```

### 2.6 `else` 的用法

`try` 成功後才要做、但本身不該被這個 `except` 保護的程式碼，放 `else`：

```python
try:
    image = decode_image_base64(b64)
except ImageDecodeError:
    return error_response("6", "base64 格式錯誤")
else:
    save_image(image)      # 這裡的錯誤不會被誤當成解碼錯誤
```

---

## 3. 業務例外（自訂例外）

service 層不碰 HTTP，用自訂例外表達「業務上的失敗」，由 API 層統一轉成回應。範本見 `assets/errors.py`：

```python
class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    title = "伺服器內部錯誤"

class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    title = "找不到資源"

# 其餘：ValidationFailedError 422、ConflictError 409、
# ExternalServiceError 502、ServiceUnavailableError 503、ServiceTimeoutError 504
```

- 依領域繼承：`DeviceOfflineError(ExternalServiceError)`、`DeviceNotFoundError(NotFoundError)`
- 例外訊息給人看；需要的資料放屬性（`self.device_id`）
- 不要用例外控制正常流程

---

## 4. 各種邊界的寫法

### 4.1 FastAPI

- endpoint 裡**不要**每支都包 `try / except Exception`，交給全域 handler（`assets/errors.py` 的 `register_exception_handlers(app)`）
- 已知的業務錯誤：service 丟 `AppError` 子類別 → handler 轉成對應 HTTP 狀態碼
- 只想回個 4xx：`raise HTTPException(status_code=404, detail="...")` 也可以，但同專案要統一
- 既有「一律 200 + status 碼」的專案：service 回傳 `Response(status="X", message="...")`，最外層仍要有 `except Exception` → `logger.exception` → 回 `"87"` 與通用訊息

### 4.2 MQTT callback（paho）

paho 預設會把 callback 的例外印出後繼續（或依設定中斷 loop），不要依賴它：

```python
def on_message(client, userdata, msg):
    try:
        handle_message(msg.topic, msg.payload)
    except Exception:
        logger.exception("處理 MQTT 訊息失敗 topic=%s", msg.topic)
```

`handle_message` 本身照 §2 的原則只抓具體例外。

### 4.3 背景任務 / thread / asyncio task

這些地方的例外**沒有人接**，不處理就會無聲消失：

```python
async def run_autofill(session_id: str) -> None:
    try:
        await AutofillService.generate(session_id)
    except Exception:
        logger.exception("背景自動填表失敗 session_id=%s", session_id)

task = asyncio.create_task(run_autofill(session_id))
background_tasks.add(task)                    # 保留參照，避免被 GC
task.add_done_callback(background_tasks.discard)
```

常駐 worker 迴圈：迴圈內 `except Exception` + `logger.exception` + 稍等再繼續，避免一筆壞資料讓整個 worker 掛掉；`asyncio.CancelledError` 不要攔（3.8+ 它不是 `Exception` 子類別，正常寫法不會攔到）。

### 4.4 main()

```python
def main() -> None:
    setup_logging()
    try:
        run()
    except KeyboardInterrupt:
        logger.info("收到中斷，結束")
    except Exception:
        logger.critical("未預期錯誤，程式結束", exc_info=True)
        raise SystemExit(1)
```

---

## 5. 外部 I/O：timeout、重試、斷線

- **每個外部呼叫都設 timeout**：`httpx.AsyncClient(timeout=10)`、`requests.get(..., timeout=10)`、`serial.Serial(..., timeout=1)`、LLM SDK 的 timeout 參數、`asyncio.wait_for(...)`
- **重試**只用在「暫時性」錯誤（timeout、連線錯誤、429、502 / 503 / 504）；400 / 401 / 404 重試沒用
- 重試要有**次數上限**與**指數退避**，每次重試 log `WARNING`，用盡 log `ERROR` 再丟例外。可用 `tenacity`（專案沒裝就手寫迴圈，不要為此新增依賴）

```python
for attempt in range(1, MAX_RETRIES + 1):
    try:
        return await client.post(url, json=body, timeout=10)
    except (httpx.TimeoutException, httpx.ConnectError):
        if attempt == MAX_RETRIES:
            logger.error("呼叫 %s 重試 %d 次仍失敗", url, MAX_RETRIES)
            raise
        delay = 2 ** attempt
        logger.warning("呼叫 %s 失敗，%s 秒後重試 (%d/%d)", url, delay, attempt, MAX_RETRIES)
        await asyncio.sleep(delay)
```

- **MQTT**：用 `reconnect_delay_set(min_delay=1, max_delay=60)`；在 `on_connect` 裡 subscribe（重連後才會重新訂閱）；`on_disconnect` 記 `WARNING`
- 硬體 / 裝置可能不在線是**常態**，不是 `ERROR`：離線用 `WARNING`，回給呼叫端明確的「裝置離線」錯誤（503 或專案的 status 碼）
