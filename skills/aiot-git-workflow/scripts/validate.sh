#!/usr/bin/env bash
# validate.sh - Validate branch name, commit message and staged files for the AIoT / Web Git workflow
#
# Usage:
#   ./validate.sh branch [branch-name]        # Validate branch name (default: current branch)
#   ./validate.sh commit "<commit-message>"   # Validate a commit message string
#   ./validate.sh staged                      # Scan staged files for secrets / junk / large files
#   ./validate.sh                             # Auto: branch + staged (if any) + last commit message

set -u

BRANCH_REGEX='^feature/[a-z][a-z0-9._-]*(_[a-zA-Z0-9._-]+)?$'
COMMIT_REGEX='^\[(feat|fix|refactor|docs|chore|test|style|perf|build|ci)\] .+ - [a-z][a-z0-9._-]*$'
PROTECTED_BRANCHES=("main" "master" "develop" "dev")
MAX_FILE_BYTES=$((5 * 1024 * 1024))

# Files that must never be committed (matched against the basename or path, case-insensitive)
SECRET_FILE_REGEX='(^|/)(\.env(\.[a-z0-9_-]+)?|credentials\.json|token\.json|auth\.json|service[-_]account[^/]*\.json|client_secret[^/]*\.json|secrets\.h|arduino_secrets\.h|id_rsa[^/]*|id_ed25519[^/]*|[^/]+\.(pem|key|p12|pfx|ovpn))$'
SECRET_FILE_ALLOW_REGEX='\.(example|sample|template)$|\.pub$'

# Files that should be ignored rather than committed
JUNK_REGEX='(^|/)(venv|\.venv|node_modules|__pycache__|\.mypy_cache|\.ruff_cache|\.pytest_cache|\.pio|\.next|logs|debug_crops|tmp_audio)/|\.pyc$|(^|/)[^/]+\.log$|(^|/)debug_[^/]*\.(jpg|jpeg|png)$|\.(pt|pth|onnx|safetensors|ckpt|h5|bin|elf|hex)$|(^|/)(\.DS_Store|Thumbs\.db|desktop\.ini)$'

# Secret-looking content in added lines
SECRET_CONTENT_REGEX='sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|xox[baprs]-[A-Za-z0-9-]{10,}|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|"private_key"[[:space:]]*:|(mqtts?|amqps?|redis|postgres(ql)?|mysql|mongodb(\+srv)?)://[^:/[:space:]]+:[^@/[:space:]]+@|username_pw_set\([[:space:]]*["'"'"'][^"'"'"']+["'"'"'][[:space:]]*,[[:space:]]*["'"'"'][^"'"'"']+["'"'"']|(ssid|password|passwd|pass|wifi_pass|mqtt_pass|api_key|apikey|secret|token)[A-Za-z_]*[[:space:]]*(\[\])?[[:space:]]*=[[:space:]]*["'"'"'][^"'"'"'<>$]{6,}["'"'"']|#define[[:space:]]+[A-Z_]*(SSID|PASS|PASSWORD|TOKEN|SECRET|API_KEY)[A-Z_]*[[:space:]]+"[^"<>]{4,}"'

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

err() { echo -e "${RED}✗ $*${NC}" >&2; }
ok()  { echo -e "${GREEN}✓ $*${NC}"; }
warn(){ echo -e "${YELLOW}⚠ $*${NC}"; }

validate_branch() {
    local branch="${1:-$(git branch --show-current 2>/dev/null)}"
    if [ -z "$branch" ]; then
        err "Cannot determine branch name"
        return 1
    fi

    for pb in "${PROTECTED_BRANCHES[@]}"; do
        if [ "$branch" = "$pb" ]; then
            err "You are on protected branch '$branch'. Do NOT commit here."
            err "Run: git checkout -b feature/<developer>_<area>"
            return 1
        fi
    done

    if [[ "$branch" =~ $BRANCH_REGEX ]]; then
        ok "Branch name '$branch' is valid"
        return 0
    else
        err "Branch name '$branch' does not match required pattern:"
        err "  feature/<developer>_<area-or-feature>"
        err "Examples: feature/shihhong_xie_mqtt-retry, feature/noah_ac-ir-sender"
        return 1
    fi
}

validate_commit_msg() {
    local msg="$1"
    local first_line
    first_line=$(printf '%s\n' "$msg" | head -n1 | tr -d '\r')

    # Skip merge / revert auto-generated messages
    if [[ "$first_line" =~ ^Merge ]] || [[ "$first_line" =~ ^Revert ]]; then
        ok "Skipping merge/revert commit"
        return 0
    fi

    if [[ "$first_line" =~ $COMMIT_REGEX ]]; then
        ok "Commit message is valid: $first_line"
        return 0
    else
        err "Commit message does not match required format:"
        err "  [<type>] <summary> - <developer>"
        err "  type: feat|fix|refactor|docs|chore|test|style|perf|build|ci"
        err "First line was: $first_line"
        echo
        err "Examples:"
        err "  [feat] 冷氣接收端支援 MQTT 設定溫度 - shihhong_xie"
        err "  [fix] MQTT 斷線後不會自動重連 - noah"
        return 1
    fi
}

validate_staged() {
    local files fail=0 f size hits
    files=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null)
    if [ -z "$files" ]; then
        warn "No staged files"
        return 0
    fi

    while IFS= read -r f; do
        [ -z "$f" ] && continue
        local lower
        lower=$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')

        if [[ "$lower" =~ $SECRET_FILE_REGEX ]] && ! [[ "$lower" =~ $SECRET_FILE_ALLOW_REGEX ]]; then
            err "Secret file staged: $f"
            err "  git restore --staged \"$f\" && echo \"$f\" >> .gitignore"
            fail=1
        fi

        if [[ "$f" =~ $JUNK_REGEX ]]; then
            err "Should be gitignored: $f"
            fail=1
        fi

        size=$(git cat-file -s ":$f" 2>/dev/null || echo 0)
        if [ "$size" -gt "$MAX_FILE_BYTES" ]; then
            err "Large file ($((size / 1024 / 1024)) MB): $f  — use Git LFS or external storage"
            fail=1
        fi
    done <<< "$files"

    # Only scan added lines, skip lock files and *.example templates
    hits=$(git diff --cached -U0 --diff-filter=ACMR -- . \
            ':(exclude)*.lock' ':(exclude)*lock.json' ':(exclude)*lock.yaml' \
            ':(exclude)*.example' ':(exclude)*.sample' 2>/dev/null \
        | awk '/^\+\+\+ /{file=substr($0,7); next} /^\+/{print file": "substr($0,2)}' \
        | grep -E -i -- "$SECRET_CONTENT_REGEX" \
        | grep -E -i -v -- 'os\.getenv|os\.environ|process\.env|getenv\(|settings\.|config\[|your[-_]|<[a-z_-]+>|example|changeme|xxx+|\*\*\*' \
        || true)
    if [ -n "$hits" ]; then
        err "Possible secrets in staged changes:"
        printf '%s\n' "$hits" | cut -c1-160 | sed 's/^/    /' >&2
        err "Move them to .env / secrets.h and read via environment variables."
        err "If this is a false positive, confirm with the user before committing."
        fail=1
    fi

    if [ "$fail" -eq 0 ]; then
        ok "Staged files look clean ($(printf '%s\n' "$files" | wc -l | tr -d ' ') files)"
    fi
    return "$fail"
}

mode="${1:-auto}"

case "$mode" in
    branch)
        validate_branch "${2:-}"
        ;;
    commit)
        if [ -z "${2:-}" ]; then
            err "Usage: $0 commit \"<message>\""
            exit 2
        fi
        validate_commit_msg "$2"
        ;;
    staged)
        validate_staged
        ;;
    auto)
        rc=0
        validate_branch || rc=1
        if [ -n "$(git diff --cached --name-only 2>/dev/null)" ]; then
            validate_staged || rc=1
        fi
        last_msg=$(git log -1 --pretty=%B 2>/dev/null || echo "")
        if [ -n "$last_msg" ]; then
            validate_commit_msg "$last_msg" || rc=1
        fi
        exit "$rc"
        ;;
    *)
        err "Unknown mode: $mode"
        err "Usage: $0 [branch|commit|staged|auto] [arg]"
        exit 2
        ;;
esac
