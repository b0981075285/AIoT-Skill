# Commit 前檢查（AIoT / Web）

每次 commit 前照順序過一遍。`scripts/validate.sh staged` 會自動做 §1、§2 的檢查；它只是第一道防線，看到可疑內容仍要自己判斷。

---

## 1. 機密（紅線 3）

### 1.1 不可 commit 的檔案

| 類型 | 檔案 |
|---|---|
| 環境變數 | `.env`、`.env.local`、`.env.production`（`.env.example` 可以） |
| 雲端 / Google 憑證 | `credentials.json`、`token.json`、`service-account*.json`、`client_secret*.json` |
| CLI / agent 登入資訊 | `auth.json`、`~/.openclaw` 底下的任何東西、OpenClaw 設定檔裡的 channel token |
| 私鑰 / 憑證 | `*.pem`、`*.key`、`*.p12`、`*.pfx`、`id_rsa*`、MQTT TLS 的 client cert / key |
| VPN | `*.ovpn` |
| 韌體帳密 | `secrets.h`、`arduino_secrets.h`（`*.example` 可以） |

### 1.2 不可出現在程式碼裡的內容

- 韌體寫死帳密：`const char* ssid = "..."`、`const char* password = "..."`、`#define WIFI_PASS "..."`
- MQTT 帳密：`client.username_pw_set("<user>", "<password>")`、`mqtt://<user>:<password>@host`（寫死真實值）
- API key：`sk-...`（OpenAI / Anthropic）、`AIza...`（Google）、`ghp_...` / `github_pat_...`（GitHub）、`xoxb-...`（Slack）、Telegram bot token（`123456789:AA...`）、LINE channel secret / access token
- DB 連線字串含密碼：`postgresql://<user>:<password>@...`（寫死真實值）

### 1.3 發現了怎麼辦

1. 先 unstage：`git restore --staged <file>`
2. 檔案類 → 加進 `.gitignore`，另外提交一份 `xxx.example`（值換成 `<your-xxx>`）
3. 程式碼類 → 改成讀環境變數：
   - Python：`os.getenv("MQTT_PASSWORD")`，搭配 `python-dotenv` 或 `pydantic-settings`
   - Node / Web：`process.env.XXX`；前端打包進瀏覽器的值等於公開，**金鑰不可放前端**，改由後端代打
   - Arduino / ESP：`#include "secrets.h"`，`secrets.h` 進 `.gitignore`，提交 `secrets.h.example`
4. 已經 commit 但還沒 push → 見 `troubleshooting.md` §5
5. 已經 push → 見 `troubleshooting.md` §6，**第一步是撤銷 / 換掉金鑰**

---

## 2. 不該進版控的檔案

| 類型 | 例子 | 處理 |
|---|---|---|
| 虛擬環境 / 依賴 | `venv/`、`.venv/`、`node_modules/` | `.gitignore` |
| 快取 / 編譯產物 | `__pycache__/`、`*.pyc`、`.mypy_cache/`、`.ruff_cache/`、`.pytest_cache/`、`dist/`、`build/`、`.next/`、`.pio/`、`*.bin`、`*.elf`、`*.hex` | `.gitignore` |
| log / 執行時資料 | `logs/`、`*.log`、`system.log`、`tmux_output.log` | `.gitignore` |
| debug 輸出 | `debug_*.jpg`、`debug_crops/`、`tmp_audio/`、錄音、截圖 | `.gitignore` |
| 大檔 | 模型權重 `*.pt` `*.onnx` `*.safetensors`、資料集、影片，或任何 > 5 MB 的檔案 | 不進 git；用 Git LFS、雲端硬碟或 release asset，README 寫下載方式 |
| 編輯器 / OS | `.vscode/`（團隊沒共用的話）、`.idea/`、`.DS_Store`、`Thumbs.db`、`desktop.ini` | `.gitignore` |
| 奇怪檔名 | 不小心把指令當檔名存出來的檔案（例如 `s -ExecutionPolicy ...`） | 刪掉 |

lock 檔（`uv.lock`、`poetry.lock`、`package-lock.json`、`pnpm-lock.yaml`）**要** commit，除非團隊明確決定不追蹤。

已經被追蹤的檔案加進 `.gitignore` 不會自動消失，要 `git rm --cached <file>` 再 commit。

---

## 3. 要不要拆 commit

`git diff --staged --stat` 看動到哪些層：

| 層 | 常見路徑 |
|---|---|
| 韌體 | `*.ino`、`*.h`、`platformio.ini`、`sketch_*/` |
| 後端 | `api/`、`controllers/`、`services/`、`dtos/`、`main.py`、`*.py` |
| 前端 | `web/`、`frontend/`、`static/`、`*.html` `*.ts` `*.tsx` `*.vue` |
| agent | OpenClaw workspace（`AGENTS.md`、`SOUL.md`、`skills/`）、`prompt/`、`prompt_config.yaml`、MCP server |
| 建置 | `Dockerfile`、`docker-compose.yml`、`requirements.txt`、`pyproject.toml`、`package.json` |

- 各層變更彼此獨立 → 拆開，`git add -p` 或 `git add <path>` 分批 stage
- 必須一起改才不會壞（同一個介面兩端）→ 可以一起，body 寫 `Breaking:`
- 依賴升級跟功能分開：`[build]` 一個 commit、`[feat]` 一個 commit
- 純格式化（ruff format、prettier 跑全專案）一定單獨一個 `[style]` commit，不然 review 看不到真正的改動

---

## 4. lint / test

**只跑專案已經設定好的**，不要自己裝工具或新增設定檔。依專案根目錄有什麼決定：

| 偵測到 | 跑什麼 |
|---|---|
| `ruff.toml` 或 `pyproject.toml` 有 `[tool.ruff]` | `ruff check .`（有 `ruff format` 慣例的話加 `ruff format --check .`） |
| `mypy.ini` 或 `[tool.mypy]` | `mypy .` |
| `tests/` 或 `test/` 且有 pytest | `pytest -q`（用 uv 的專案：`uv run pytest -q`） |
| `package.json` 有 `lint` / `typecheck` / `test` / `build` script | `npm run lint`、`npm run build` 等對應 script |
| `platformio.ini` | `pio run` |
| `*.ino` 且有 `arduino-cli` | `arduino-cli compile --fqbn <board> <sketch-dir>` |

- 只改 docs / agent-log 可以跳過
- 失敗就回報原始輸出，問使用者要先修還是照樣 commit；不要說「測試通過」除非真的跑過且通過
- 需要接硬體才能驗的改動，在 PR 描述寫「已實機測試 / 未實機測試」

---

## 5. 最後確認

```bash
git status
git diff --staged --stat
bash scripts/validate.sh staged
bash scripts/validate.sh commit "<message>"
```
