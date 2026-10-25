---
description: 驗證目前分支名稱、已 stage 的檔案（機密 / 垃圾檔 / 大檔）與最後一筆 commit message 是否符合 AIoT / Web Git 規範
argument-hint: "[branch <name> | commit \"<msg>\" | staged]（留空則自動檢查全部）"
---

在使用者目前的專案根目錄，執行 aiot-git-workflow plugin 內的驗證腳本。

```
bash "${CLAUDE_PLUGIN_ROOT}/skills/aiot-git-workflow/scripts/validate.sh" $ARGUMENTS
```

未帶參數時會檢查目前分支、已 stage 的檔案（有的話）與最後一筆 commit。把腳本輸出原樣回報給使用者；若出現 ✗，依 `aiot-git-workflow` skill 的規範簡述如何修正（機密類看 `references/pre-commit.md` §1）。
