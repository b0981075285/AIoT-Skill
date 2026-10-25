# Rebase、衝突與常見狀況

團隊一律用 rebase 同步 develop，保持歷史線性。整合分支是 `dev` 的專案把 `develop` 換掉。

---

## 1. feature 分支 rebase 到最新 develop

```bash
git fetch origin
git log origin/develop --oneline -10     # 先看要拉進來什麼
git rebase origin/develop
```

是 `origin/develop`（斜線），不是 `origin develop`（空格）。

---

## 2. rebase 衝突

```bash
# 編輯衝突檔案（<<<<<<< ======= >>>>>>>）
git add <conflicted-files>
git rebase --continue
# 重複直到完成；想放棄：
git rebase --abort
```

IoT / Web 常見衝突：

| 檔案 | 處理 |
|---|---|
| `uv.lock` / `poetry.lock` / `package-lock.json` | 不要手動合。先取 develop 版（rebase 中 ours 是 develop、theirs 是你的 commit，所以用 `git checkout --ours <lock>`），再重跑 `uv lock` / `npm install` 產生新的 lock，`git add` |
| `requirements.txt` / `pyproject.toml` | 兩邊新增的套件都保留，版本取較新的 |
| `docker-compose.yml` | 注意 port、service 名稱不要重複 |
| `.ino` / 韌體 pin 定義 | 確認兩邊沒有搶同一支腳位 |

rebase 完、push 前至少跑一次 lint / test（`pre-commit.md` §4）。

---

## 3. rebase 後 force push

```bash
git push -f origin feature/<your-branch>
```

只限自己的 feature 分支。多人共用的 feature 分支用 `git push --force-with-lease`，避免蓋掉對方剛推的 commit。

---

## 4. 不小心 commit 到 develop / main（還沒 push）

```bash
git log --oneline -5                       # 記下要搬的 commit
git checkout -b feature/<developer>_<area> # 新分支會帶著這些 commit
git checkout develop
git reset --hard origin/develop            # develop 回到遠端狀態
git checkout feature/<developer>_<area>
```

`reset --hard` 前先 `git status` 確認沒有未 commit 的改動。

---

## 5. 機密已經 commit，還沒 push

最後一個 commit：

```bash
git rm --cached .env                       # 檔案留在本機，從版控移除
echo ".env" >> .gitignore
git add .gitignore
git commit --amend --no-edit
```

在更早的 commit：

```bash
git rebase -i <機密 commit 的前一個>^     # 互動模式在此環境不可用時，請使用者自己在終端機執行
# 把該 commit 標 edit → git rm --cached <file> → git commit --amend → git rebase --continue
```

處理完用 `git log -p --all -S "<金鑰片段>"` 確認歷史裡真的沒有了，再 push。

---

## 6. 機密已經 push 了

**順序很重要，先換金鑰再清歷史**——推上去的瞬間就該假設已外洩（GitHub 會被爬蟲秒掃）。

1. **立即撤銷 / 換掉**：API key 到後台 revoke；Google `credentials.json` 刪掉 service account key；WiFi / MQTT 密碼改掉；Telegram / LINE / Discord bot token 重新產生；OpenClaw 綁定的 channel token 重發
2. 確認新金鑰只放在 `.env` / `secrets.h`，舊的已經失效
3. 在 feature 分支上照 §5 移除並 force push
4. 如果已經合進 develop / main：不可自己 force push（紅線 1），通知 repo 管理者用 `git filter-repo` 或 BFG 清歷史，並請所有人重新 clone
5. 公開 repo 另外到 GitHub 申請清除 cached views

只做第 3、4 步不做第 1 步 = 沒處理。

---

## 7. 想放棄本機改動，對齊遠端

```bash
git status                                 # 確認要丟的是什麼
git fetch origin
git reset --hard origin/<branch>
```

無法還原，執行前跟使用者確認。只想丟某個檔案：`git restore <file>`。

---

## 8. 開發到一半要切分支

```bash
git stash push -u -m "wip: <描述>"         # -u 連未追蹤檔一起
git checkout other-branch
# ...
git checkout feature/<your-branch>
git stash pop
```

---

## 9. FAQ

### 為什麼用 rebase 不用 merge

merge 會產生額外 merge commit，多人時 graph 很亂；rebase 讓 feature 的 commit 接在最新 develop 後面，歷史一條線。

### 韌體跟後端在同一個 repo 還是分開？

都可以。同一個 repo（monorepo）時用 `firmware/`、`backend/`、`web/`、`agent/` 分目錄，commit 依 `pre-commit.md` §3 分層；分開的 repo，介面變更在兩邊 PR 都寫 `Breaking:` 並互相附連結。

### 一人一條 feature 分支可以嗎？

可以（`feature/<developer>`）。合併後不刪，定期 `git pull --rebase origin develop` 跟上。不要拿它跟別人的 feature 分支互相 merge。
