# PR/MR 完整流程

從開分支到合併、清理，再到 develop → main release。整合分支若是 `dev`，把下文的 `develop` 換掉即可（`SKILL.md` §2）。

---

## 1. 從最新 develop 開 feature 分支

```bash
git checkout develop
git pull --ff-only
git checkout -b feature/<developer>_<area>
```

---

## 2. 開發與提交

按功能單元 commit，每個 commit 先過 `references/pre-commit.md`，格式符合 `SKILL.md` §3.2。

---

## 3. 推送並建立 PR/MR

### 3.1 推送

```bash
git push -u origin feature/<developer>_<area>
```

### 3.2 建立 PR/MR

- **Source**：`feature/<developer>_<area>`，**Target**：`develop`
- 標題沿用 commit 格式：`[<type>] <簡述> - <developer>`
- 有 `gh`（GitHub）或 `glab`（GitLab）時可直接開：

  ```bash
  gh pr create --base develop --title "[feat] ... - <developer>" --body-file <file>
  glab mr create --target-branch develop --title "[feat] ... - <developer>" --description "..."
  ```

- 說明欄範本：

  ```markdown
  ## 變更
  - ...

  ## 影響範圍
  - [ ] 韌體  - [ ] 後端  - [ ] 前端  - [ ] OpenClaw / agent  - [ ] Docker / 部署

  ## Breaking（介面變更，沒有就刪掉）
  - MQTT topic / payload：
  - API：
  - .env 新增變數：

  ## 測試
  - [ ] lint / unit test
  - [ ] 本機跑起來實測
  - [ ] 實機（硬體）測試
  ```

- 勾選合併後自動刪除來源分支

---

## 4. PR/MR 後續變更

review 修正、解衝突、跟上 develop：

1. 在 feature 分支新增 commit，或 rebase 到 `origin/develop`（`troubleshooting.md` §1–§3）
2. rebase 後 `git push -f origin feature/<developer>_<area>`（只限自己的 feature 分支）
3. 平台自動更新 PR/MR

---

## 5. 合併後本地清理

```bash
git checkout develop
git pull --ff-only
git branch -d feature/<developer>_<area>
git remote prune origin
```

一人一條長期 `feature/<developer>` 分支的用法：合併後不刪，改成 `git pull --rebase origin develop` 跟上再繼續開發。

---

## 6. develop → main release

### 6.1 前置條件

- 預定進 release 的 PR/MR 都已合併
- CI 在 `develop` 全綠
- 有硬體的專案：韌體已在實機上驗過；有 `Breaking:` 的變更，所有相依元件都已更新

### 6.2 確認範圍

```bash
git checkout develop && git pull --ff-only
git checkout main && git pull --ff-only
git log --oneline origin/main..origin/develop
git log origin/main..origin/develop --grep "Breaking:"     # 列出有介面變更的 commit
```

### 6.3 建立 PR/MR

- Source `develop` → Target `main`，標題 `Release vX.Y.Z`
- 說明列出功能、修正、Breaking 變更、部署注意事項（`.env` 新變數、DB migration、韌體要重燒）

### 6.4 合併與打 tag

```bash
git checkout main
git pull --ff-only
git tag -a v<X.Y.Z> -m "Release v<X.Y.Z>"
git push origin v<X.Y.Z>
```

推 tag 不是推 main，不違反紅線；main 本身只能透過 PR/MR 更新。
