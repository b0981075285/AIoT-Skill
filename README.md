# AIoT-Skill

AIoT / Web 團隊的 Git 協作規範，打包成 **Claude Code / Codex CLI plugin**。

| Skill | 內容 |
|-------|------|
| **aiot-git-workflow** | main/develop/feature 分支、commit 格式、commit 前機密與垃圾檔掃描、跨層（韌體 / 後端 / 前端 / agent）拆 commit、介面變更 `Breaking:` 標註、PR/MR 與 release 流程 |

> 適用：Python 後端（FastAPI、MQTT、Docker）、OpenClaw / MCP agent、環控韌體（Arduino / ESP32 / Raspberry Pi）、Web 前端。
> Android 專案請改用 [imac-git-workflow](https://github.com/noalowo/android_skill)；兩者 commit 格式相同。

---

## 規範重點

```
[<type>] <主要變更簡述> - <developer>

Add:
- ...
Breaking:
- home/sensor/temp payload 改成 JSON，所有訂閱者都要更新
```

- type：`feat` `fix` `refactor` `docs` `chore` `test` `style` `perf` `build` `ci`
- 分支：`feature/<developer>_<area>`，從 `develop`（或 `dev`）開出，PR/MR 回去
- 紅線：不直接 push `main` / `develop`、feature 不互相 merge、**不 commit 機密**

完整規則見 [`skills/aiot-git-workflow/SKILL.md`](skills/aiot-git-workflow/SKILL.md)。

---

## 安裝

### Claude Code（Plugin Marketplace）

```
/plugin marketplace add b0981075285/AIoT-Skill
/plugin install aiot-git-workflow@aiot-skills
```

- 驗證：`/plugin` 看到 `aiot-git-workflow@aiot-skills` 為 enabled，或 `/skills` 列出 `aiot-git-workflow`
- 更新：`/plugin marketplace update aiot-skills`

### Claude Code（手動複製）

把 `skills/aiot-git-workflow/` 整個資料夾複製到 `C:/Users/<username>/.claude/skills/`（或專案內的 `.claude/skills/`）。

### Codex CLI（Plugin）

```
codex plugin marketplace add b0981075285/AIoT-Skill
codex plugin add aiot-git-workflow@aiot-skills
```

- 驗證：`codex plugin list` 看到 `aiot-git-workflow`
- 更新：`codex plugin marketplace upgrade aiot-skills`

### Codex CLI（手動 / fallback）

- 把 `skills/aiot-git-workflow/` 複製到 `~/.agents/skills/`（使用者層級）或專案的 `.agents/skills/`
- 或只用 instruction：把本 repo 的 `AGENTS.md` 複製到專案根目錄，或放 `~/.codex/AGENTS.md` 當全域規範

### 其他 agent

- **Gemini CLI**：`skills/aiot-git-workflow/` 複製到 `~/.gemini/skills/`
- **Antigravity / OpenClaw / 其他吃 AGENTS.md 的 agent**：複製 `AGENTS.md` 到專案根目錄或 agent workspace

### 設定開發者名稱

commit message 結尾的名稱依序取 `git config aiot.developer`、`git config imac.developer`、`git config user.name` 中第一個純小寫英數（可含 `.` `_` `-`）的值。`user.name` 是中文或有大寫時設定一次即可，不影響 commit 作者顯示名：

```
git config --global aiot.developer <your-name>
```

已經為 Android skill 設過 `imac.developer` 的人不用再設。

---

## 驗證腳本與 slash 指令

```bash
bash skills/aiot-git-workflow/scripts/validate.sh                   # 分支 + staged 檔案 + 最後一筆 commit
bash skills/aiot-git-workflow/scripts/validate.sh branch [name]
bash skills/aiot-git-workflow/scripts/validate.sh commit "<msg>"
bash skills/aiot-git-workflow/scripts/validate.sh staged            # 掃機密、垃圾檔、> 5 MB 大檔
```

`staged` 會擋：`.env`、`credentials.json`、`auth.json`、私鑰、`secrets.h`、`*.ovpn`；`venv/`、`__pycache__/`、`node_modules/`、log、`debug_*.jpg`、模型權重、韌體編譯產物；以及新增程式碼裡的 API key、bot token、韌體寫死的 WiFi / MQTT 帳密、含密碼的連線字串。

Claude Code 安裝 plugin 後可用 `/aiot-validate [branch|commit|staged]` 手動執行。

Windows 請在 Git Bash 執行。

---

## 目錄結構

```
AIoT-Skill/
├── README.md
├── LICENSE
├── AGENTS.md                         # Codex / Gemini / Antigravity / OpenClaw 用的精簡規範
├── check_skills.sh                   # 檢查 SKILL.md frontmatter
├── .claude-plugin/                   # Claude Code plugin + marketplace
├── .codex-plugin/plugin.json         # Codex plugin
├── .agents/plugins/marketplace.json  # Codex marketplace
├── commands/aiot-validate.md         # Claude Code slash 指令
└── skills/aiot-git-workflow/
    ├── SKILL.md
    ├── examples/commit_messages.md   # type 對照表、各層範例、不合法範例
    ├── references/
    │   ├── pre-commit.md             # 機密、垃圾檔、拆 commit、lint / test
    │   ├── workflow.md               # 開分支 → PR/MR → release
    │   └── troubleshooting.md        # rebase、衝突、機密外洩處理
    └── scripts/validate.sh
```

維護時提交前跑 `bash check_skills.sh`。
