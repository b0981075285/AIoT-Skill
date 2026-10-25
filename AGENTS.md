# AIoT / Web 團隊 Git 規範（AGENTS.md）

給讀取 `AGENTS.md` 的 agent（Codex、Antigravity、Gemini、OpenClaw 等）使用的常駐精簡規範。
完整內容以 `skills/aiot-git-workflow/SKILL.md` 為準；衝突時以 skill 為準。
適用：Python 後端（FastAPI、MQTT、Docker）、OpenClaw / MCP agent、環控韌體（Arduino / ESP32 / Raspberry Pi）、Web 前端。動手前先讀專案自己的 `CLAUDE.md` / `AGENTS.md`（若存在）。

## 1. 紅線

- **禁止**對 `main`、`develop`（或 `dev`）直接 push / force push；**禁止** feature 分支互相 merge。
- **禁止** commit 機密：`.env`、`credentials.json`、`auth.json`、`*.pem` / `*.key`、`secrets.h`、韌體寫死的 WiFi / MQTT 帳密、API key、bot / channel token。改用環境變數或 `secrets.h` + `.example` 範本。已經 push 的機密：先撤銷金鑰，再清歷史。

## 2. 分支

- `main`（release）、`develop` 或 `dev`（整合，以 repo 實際存在的為準）、`feature/<developer>_<area>`（例：`feature/shihhong_xie_mqtt-retry`）。
- 從最新 develop 開分支，PR/MR 回 develop；同步 protected 分支用 `git pull --ff-only`，feature 跟上 develop 用 `git pull --rebase origin develop`。

## 3. Commit message

```
[<type>] <主要變更簡述> - <developer>

Add: / Fix: / Refactor: / Breaking:   （選配條列）
```

- type ∈ `feat / fix / refactor / docs / chore / test / style / perf / build / ci`，小寫、`[]` 包住。
- 依賴版本、Dockerfile、compose → `build`；CI → `ci`；agent-log、README → `docs`；`.gitignore`、設定檔整理 → `chore`。
- 改到其他元件依賴的介面（MQTT topic / payload、API 欄位、DB schema、`.env` 變數、OpenClaw tool 名稱）必須在 body 寫 `Breaking:`。
- `<developer>` 依序取 `git config aiot.developer`、`git config imac.developer`、`git config user.name` 中第一個純小寫英數（可含 `.` `_` `-`）的值；都不符合才問使用者，建議 `git config --global aiot.developer <name>`。
- 例：`[feat] 冷氣接收端支援 MQTT 設定溫度 - shihhong_xie`

## 4. Commit 前

1. 不在 protected 分支上。
2. 看 `git diff --staged` 寫簡述，描述行為不寫檔名。
3. 跑 `bash skills/aiot-git-workflow/scripts/validate.sh staged`（機密、venv / `__pycache__` / log / debug 圖、> 5 MB 大檔）。
4. 韌體 / 後端 / 前端 / agent 各層獨立的改動拆成不同 commit。
5. 專案有設定的 lint / test 才跑（ruff、mypy、pytest、npm run lint / build、pio run），失敗如實回報。
6. `validate.sh commit "<msg>"` 通過後才 commit。
