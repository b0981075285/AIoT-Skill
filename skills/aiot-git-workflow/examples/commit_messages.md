# Commit Message 範例集（AIoT / Web）

格式：`[<type>] <簡述> - <developer>`。body 的 `Add:` / `Fix:` / `Refactor:` / `Breaking:` 為選配。規則詳見 `SKILL.md` §3.2。

---

## 1. type 怎麼選

| 改了什麼 | type |
|---|---|
| 新功能：新 API、新 MQTT topic、新感測器 / 致動器、新頁面、新 OpenClaw skill / tool / channel | `feat` |
| 修 bug：斷線不重連、payload 解析錯、溫度單位錯、前端顯示錯、agent 呼叫錯 tool | `fix` |
| 行為不變的重構：拆 service、整理 controller、抽共用 MQTT client | `refactor` |
| 效能：降低輪詢頻率、批次寫 DB、減少韌體記憶體、前端 bundle 變小 | `perf` |
| 依賴版本（`requirements.txt` `pyproject.toml` `uv.lock` `package.json`）、`Dockerfile`、`docker-compose.yml`、韌體 library / board 版本 | `build` |
| GitHub Actions、GitLab CI | `ci` |
| 測試：pytest、前端測試、MQTT mock、硬體 loopback 測試腳本 | `test` |
| README、API 文件、接線圖、agent-log、開發筆記 | `docs` |
| 純格式：ruff format、prettier、縮排 | `style` |
| 雜項：`.gitignore`、`.env.example`、`ruff.toml`、OpenClaw 設定檔（不含行為改變）、搬檔案 | `chore` |

判斷原則：

- **OpenClaw prompt / `SOUL.md` / `AGENTS.md` 等人設與指令檔**：讓 agent 多會一件事 → `feat`；修正 agent 做錯的事 → `fix`；只是整理措辭 → `refactor`
- **改了 `.env.example` 新增變數**：跟著功能一起進 `feat` / `fix`，並在 body 寫 `Breaking:`（其他人要補 `.env`）
- **安全性修補**（升級有漏洞的套件）：`build`；修程式碼裡的漏洞：`fix`
- 一個 commit 混了兩種 → 選影響比較大的那個當 type，簡述用 `+` 連接（見 §3 最後一例）

---

## 2. 依層別的範例

### Python 後端（FastAPI / service）

```
[feat] 新增 /api/devices/{id}/status 查詢裝置最新狀態 - shihhong_xie
```

```
[fix] 上傳圖片超過 5MB 時回 500 改成回 413 - shihhong_xie

Fix:
- 在 controller 先檢查 Content-Length
- 錯誤訊息改成前端可顯示的中文
```

```
[refactor] 假 API 簡化成一個 session 一次回傳全部事件與圖片 - shihhong_xie
```

### MQTT / 環控

```
[feat] 冷氣接收端支援 MQTT 設定溫度與模式 - shihhong_xie

Add:
- 訂閱 home/ac/<room>/set，payload 為 {"temp": 26, "mode": "cool"}
- 執行完回報到 home/ac/<room>/state
```

```
[fix] MQTT broker 重啟後 client 不會重連 - noah

Fix:
- paho client 改用 loop_start + reconnect_delay_set
- on_connect 內重新 subscribe
```

```
[refactor] 溫濕度 topic 改成依房間分層 - alice

Refactor:
- home/sensor/temp → home/<room>/sensor/temp

Breaking:
- 舊 topic home/sensor/temp 不再發布，後端訂閱與前端圖表要改用新 topic
```

### 韌體（Arduino / ESP32 / Raspberry Pi）

```
[feat] IR 發射端新增送風模式代碼 - shihhong_xie
```

```
[fix] ESP32 開機時 WiFi 連不上會卡死改成重試三次後重開機 - bob
```

```
[chore] WiFi 與 MQTT 帳密移到 secrets.h 並加入 gitignore - shihhong_xie

Add:
- secrets.h.example 範本
```

### OpenClaw / agent

```
[feat] OpenClaw 新增查詢冷氣狀態的 skill - shihhong_xie

Add:
- skills/ac-status/SKILL.md
- 呼叫後端 /api/devices/{id}/status
```

```
[fix] agent 收到「關冷氣」時誤呼叫 set_temp 改為呼叫 power_off - noah
```

```
[feat] MCP server 新增 modify_quotation tool - alice

Breaking:
- quotation tool 的 amount 欄位改為整數（單位：元）
```

### Web 前端

```
[feat] 儀表板新增各房間溫濕度即時折線圖 - alice
```

```
[fix] WebSocket 斷線後頁面不再更新改成自動重連 - bob
```

### 建置 / 部署 / 文件

```
[build] 升級 certifi 到 2026.10.23 修補漏洞 - shihhong_xie
```

```
[build] 後端改用 docker compose 一起啟動 mosquitto - noah

Add:
- docker-compose.yml 新增 mosquitto service 與 volume

Breaking:
- 後端 MQTT_HOST 預設改為 mosquitto，本機開發需在 .env 設 127.0.0.1
```

```
[ci] GitHub Actions 加入 ruff 與 pytest - alice
```

```
[docs] 補上 10-23 自動填表改由 STT 開啟的 agent-log - shihhong_xie
```

---

## 3. 跨層變更

能拆就拆，每層一個 commit，依相依順序提交（先後端 / 協定，再韌體、前端、agent）：

```
[feat] 後端新增冷氣排程 API - shihhong_xie
[feat] 儀表板新增冷氣排程設定頁 - shihhong_xie
[feat] OpenClaw 新增「幾點開冷氣」排程 skill - shihhong_xie
```

兩端不一起改就會壞（例如 payload 格式改了），可以合成一個 commit，但一定要寫 `Breaking:`：

```
[refactor] 溫度 payload 從純數字改成 JSON 並帶時間戳 + 修正單位錯誤 - shihhong_xie

Refactor:
- pub.py 發布 {"value": 25.5, "unit": "C", "ts": 1729850000}
- 後端 subscriber 改解析 JSON

Fix:
- 原本韌體送華氏、後端當攝氏處理

Breaking:
- home/sensor/temp payload 格式改變，所有訂閱者都要更新
```

---

## 4. 不合法範例

| 訊息 | 問題 |
|---|---|
| `update` | 缺 type、缺 developer、沒說改什麼 |
| `Update main.py` | 同上，只寫檔名 |
| `[feat] 修改 main.py - noah` | 簡述只寫檔名，要寫行為 |
| `[feat] 新增溫度感測` | 缺 ` - developer` |
| `feat: 新增溫度感測 - noah` | type 要用 `[]` |
| `[Feat] 新增溫度感測 - noah` | type 必須小寫 |
| `[feat]新增溫度感測 - noah` | `]` 後缺空格 |
| `[feat] 新增溫度感測- noah` | `-` 前後要空格 |
| `[feat] 新增溫度感測 - Noah` | developer 必須小寫 |
| `[hotfix] 修正重連 - noah` | 沒有 `hotfix` 這個 type，用 `fix` |
