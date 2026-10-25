---
name: aiot-git-workflow
description: "AIoT / Web team Git workflow for Python backends (FastAPI, MQTT, Docker), OpenClaw agents, environment-control firmware (Arduino / ESP / Raspberry Pi) and web frontends. Use for branch creation, commits, PR/MR open or update, rebase, conflict resolution, merging to develop or main. MUST trigger whenever the user is about to commit in an IoT, backend, agent or web project, to enforce commit message format and block secrets (.env, credentials.json, WiFi / MQTT passwords, API tokens) from being committed. Triggers on Chinese: commit / 提交 / commit message 格式 / 開新分支 / 開 PR / 開 MR / rebase develop / 解衝突 / 合併到 develop / 合併到 main / force push / 推上去. Do not trigger for Android projects (use imac-git-workflow) or unrelated git questions."
version: 1.0.0
---

# AIoT / Web 團隊 Git 協作規範

本 skill 規範 AIoT（Python 後端、MQTT、OpenClaw、環控韌體）與 Web 專案在 main / develop / feature 三分支模型下的協作流程，GitLab 與 GitHub 皆適用。commit 格式與 Android 團隊的 `imac-git-workflow` 完全相同，跨團隊看 log 時一致；差別在於 IoT / Web 專案多了 **機密外洩**、**多層（韌體 / 後端 / 前端 / agent）同時改動**、**通訊協定變更** 這幾個風險，本 skill 額外規範這些。

---

## 0. 觸發後第一件事

| 使用者意圖 | 動作 |
|---|---|
| 要 commit、產生 commit message、檢查 commit 草稿 | 照 §6 流程；type 怎麼選看 `examples/commit_messages.md` |
| commit 前檢查（機密、垃圾檔、lint、拆 commit） | 讀 `references/pre-commit.md`，跑 `scripts/validate.sh staged` |
| 開 feature 分支、推送、建立 PR/MR、合併後清理、develop → main release | 讀 `references/workflow.md` |
| rebase、解衝突、force push、機密已經 commit / push 了、commit 跑錯分支 | 讀 `references/troubleshooting.md` |
| 確認 GitHub / GitLab 專案設定 | 讀本檔 §5 |

簡單問題不需要全讀，定位到對應章節即可。

---

## 1. 紅線（絕不可違反）

使用者要求做下列任一項時，直接拒絕並說明理由：

1. 禁止對 `main` 或整合分支（`develop`，或專案使用的 `dev`）直接 `git push` 或 `git push -f`
2. 禁止 feature 分支互相 merge（例如 `feature/a` merge 到 `feature/b`）
3. 禁止 commit 機密：`.env`、`credentials.json`、`auth.json`、私鑰 / 憑證（`*.pem` `*.key` `*.p12`）、韌體裡寫死的 WiFi / MQTT 帳密、API key、OpenClaw 的 channel / bot token。發現時停止 commit，引導改用環境變數或 `secrets.h` / `.env` + `.example` 範本（見 `references/pre-commit.md` §1）

前兩條會污染歷史或丟失他人 commit；第三條一旦 push 就只能撤銷金鑰，改歷史也救不回來。

---

## 2. 分支模型

```
main                         release 版本（protected）
develop（或 dev）             整合區（protected）
feature/<developer>_<area>   個人開發分支
```

- 整合分支名稱以 repo 實際存在的為準：先 `git branch -r` 看遠端有 `origin/develop` 還是 `origin/dev`，之後所有指令用那一個。下文一律寫 `develop`
- 所有 feature 分支從最新的 `develop` 開出，只 PR/MR 回 `develop`
- PR/MR 合併後刪除來源 feature 分支
- `develop` → `main` 走 PR/MR，產生 merge commit，合併後在 `main` 打 tag

---

## 3. 命名規則

### 3.1 分支名

```
feature/<developer>_<area-or-feature-in-english>
```

- `<developer>`：開發者英文名，純小寫英數（可含 `.` `_` `-`）
- `<area-or-feature>`：英文功能描述，建議帶上層別讓人一眼看出改哪裡

合法：
```
feature/shihhong_xie
feature/shihhong_xie_mqtt-retry
feature/noah_ac-ir-sender
feature/alice_openclaw-line-channel
feature/bob_web-dashboard
```

不合法：
```
feature/冷氣控制            # 不可用中文
shihhong_mqtt              # 缺 feature/ 前綴
feature/Noah_api           # developer 必須小寫
```

一人一條長期 `feature/<developer>` 分支的用法（只有 developer 沒有 area）也可接受，validate.sh 會放行。

### 3.2 Commit message

格式：

```
[<type>] <當下主要變更的簡述> - <developer>

Add:
- ...
Fix:
- ...
Refactor:
- ...
Breaking:
- ...
```

- 第一行必填：type 小寫並用 `[]` 包住，`]` 後一個空格，結尾 ` - <developer>` 不可省略
- type 固定 10 種：`feat` `fix` `refactor` `docs` `chore` `test` `style` `perf` `build` `ci`
- 簡述用中文或英文皆可，講「改了什麼行為」，不要只寫檔名（✗ `修改 main.py`）
- body 條列為選配，有多項變更才加
- **`Breaking:` 為 IoT / Web 專屬**：只要改到「別的元件依賴的介面」就必須寫，讓韌體、後端、前端、agent 的負責人知道要跟著改：
  - MQTT topic 名稱、payload 欄位 / 單位 / 型別、QoS、retain
  - REST / WebSocket API 路徑、request / response 欄位
  - DB schema、`.env` 變數新增或改名、Docker port / volume
  - OpenClaw tool / skill 名稱或參數
- `<developer>` 強制小寫

**取得 developer 名稱**：不要每次問使用者，依序執行，採用第一個純小寫英數（可含 `.` `_` `-`）的值：

1. `git config aiot.developer`
2. `git config imac.developer`（與 Android 團隊共用的設定，已設過就直接用）
3. `git config user.name`
4. 都沒有或不符合（中文、空格、大寫）→ 問使用者一次，並建議 `git config --global aiot.developer <name>` 保存

範例：
```
[feat] 冷氣接收端支援 MQTT 設定溫度 - shihhong_xie
[fix] MQTT 斷線後不會自動重連 - shihhong_xie
[build] 升級 certifi 到 2026.10.23 修補漏洞 - shihhong_xie
```

不合法：
```
修正 bug                          # 缺 type、缺 developer
[feat] 新增溫度感測               # 缺 developer
feat: 新增溫度感測 - noah          # 應為 [feat]
[Fix] 修正重連 - noah              # type 必須小寫
[fix] 修正重連 - Noah              # developer 必須小寫
```

驗證：`scripts/validate.sh commit "<message>"`。

---

## 4. 標準指令模板

```bash
# 開新 feature 分支
git checkout develop
git pull --ff-only
git checkout -b feature/<developer>_<area>

# 同步 protected 分支
git checkout <branch>
git pull --ff-only

# feature 分支跟上最新 develop
git pull --rebase origin develop

# 合併後清理
git checkout develop
git pull --ff-only
git branch -d feature/<developer>_<area>
git remote prune origin
```

`--ff-only` 失敗時：工作目錄有未提交改動 → 先 `git stash`；本地與遠端分歧 → 先 `git log origin/<branch>..<branch>` 看多了什麼，確認要丟才 `git fetch origin && git reset --hard origin/<branch>`。`reset --hard` 無法還原，執行前要跟使用者確認。

---

## 5. 平台設定

只在專案尚未設定時動手，先檢查現況。

| 項目 | GitHub | GitLab |
|---|---|---|
| 分支保護 | Settings → Branches，對 `main`、`develop` 建規則 | Settings → Repository → Protected branches |
| 合併方式 | 只開 Allow merge commits，關 squash / rebase merging | Merge method 選 merge commit，關 squash |
| 合併後刪分支 | Automatically delete head branches | 建 MR 時勾 Delete source branch |
| 機密掃描 | Settings → Code security → Secret scanning / Push protection 開啟 | Secure → Secret detection（視方案） |

---

## 6. Commit 時的行為

使用者要 commit、要你產生 commit message、或貼草稿給你看時，依序：

1. **分支**：`git branch --show-current`。在 `main` / `develop` / `dev` 上 → 依紅線拒絕，引導 `git checkout -b feature/<developer>_<area>`（未 commit 的改動會跟著帶過去）
2. **分支名**：符合 §3.1
3. **看改了什麼**：`git status` + `git diff --staged`（沒 stage 的話看 `git diff`）。以 diff 為準寫簡述，不要只憑使用者的一句話
4. **機密與垃圾檔**：跑 `scripts/validate.sh staged`。有 ✗ 就停下來處理，不可直接 commit（`references/pre-commit.md` §1、§2）
5. **要不要拆**：同時改到多個層（韌體 / 後端 / 前端 / OpenClaw）且彼此獨立 → 拆成多個 commit；同一個介面變更兩端必須一起改才能動 → 可以一個 commit，body 寫 `Breaking:`（`references/pre-commit.md` §3）
6. **lint / test**：專案有設定才跑（ruff、mypy、pytest、npm run lint / build、arduino-cli compile…），沒設定就跳過，不要自己裝工具（`references/pre-commit.md` §4）。失敗要回報，不要假裝通過
7. **developer 名稱**：依 §3.2 取得
8. **產生 message**：依 §3.2，type 依 `examples/commit_messages.md` 的對照表選；`scripts/validate.sh commit "<msg>"` 驗證後才 commit
9. **使用者說「推上去」**：只推自己的 feature 分支，`git push -u origin <feature 分支>`；要合進 develop 就開 PR/MR（`references/workflow.md` §3）
