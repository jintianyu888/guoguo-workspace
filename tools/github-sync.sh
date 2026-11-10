#!/bin/bash
# github-sync.sh —— 把「代码+文档」同步到私有仓库（2026-11-10 立）
# 只纳入：workspace 根脚本与文档、面板源码；绝不纳入 state/data/密钥/数据库/备份包。
# 用法：--local（只同步+本地提交）｜--push（再推送）｜--dry-run
set -u
W=/home/j/.openclaw/workspace
REPO=/home/j/openclaw-git/guoguo
PANEL=/home/j/openclaw-workspaces/work/果果助手
ENVF=/home/j/.config/guoguo/github.env
LOG=$W/state/work/github-sync.log
MODE="${1:---local}"
log(){ echo "[$(date '+%F %T')] $*" >>"$LOG"; }

mkdir -p "$REPO"/{tools,panel,docs} "$(dirname "$LOG")"
cd "$REPO" || exit 1
[ -d .git ] || { git init -q -b main; log "init repo"; }

# —— 1) 同步文件（先清空纳入目录，避免残留）——
if [ "$MODE" != "--dry-run" ]; then
  rm -rf tools docs panel
  mkdir -p tools docs panel
  cp -f "$W"/tools/*.sh "$W"/tools/*.py "$W"/tools/*.js tools/ 2>/dev/null
  cp -f "$W"/docs/*.md docs/ 2>/dev/null
  cp -f "$W"/AGENTS.md "$W"/SOUL.md "$W"/IDENTITY.md "$W"/USER.md "$W"/MEMORY.md . 2>/dev/null
  cp -f "$PANEL/server.js" panel/ 2>/dev/null
  for f in index.html overview.html; do [ -f "$PANEL/public/$f" ] && cp -f "$PANEL/public/$f" panel/; done
  for f in "$PANEL"/public/*.css "$PANEL"/public/*.js; do [ -f "$f" ] && cp -f "$f" panel/; done
  printf '%s\n' "state/" "data/" "media/" "*.db" "*.sqlite" "*.sqlite3" "*.tar.gz" "*.zip" "*.bak*" ".env" "secrets*" "venv/" "*-venv/" "node_modules/" "*.png" "*.jpg" "*.log" > .gitignore
fi

# —— 2) 敏感串扫描（命中即中止，不提交）——
HITS=$(grep -rInE 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----'   --include='*.sh' --include='*.py' --include='*.js' --include='*.md' --include='*.html' . 2>/dev/null | grep -v 'secret-contract' | head -20)
if [ -n "$HITS" ]; then
  echo "❌ 敏感串扫描命中，已中止：" >&2
  echo "$HITS" >&2
  log "ABORT secret-scan hits=$(printf '%s\n' "$HITS" | wc -l)"
  exit 2
fi

if [ "$MODE" = "--dry-run" ]; then
  echo "dry-run：将纳入 $(find . -type f -not -path './.git/*' | wc -l) 个文件，敏感串 0"
  exit 0
fi

git add -A
if git diff --cached --quiet; then
  echo "无变更"; log "no-change"; exit 0
fi
git -c user.name=guoguo -c user.email=guoguo@localhost commit -q -m "sync $(date '+%F %H:%M') 脚本与文档快照"
SHA=$(git rev-parse --short HEAD)
CNT=$(git ls-files | wc -l)
SIZE=$(du -sh --exclude=.git . | cut -f1)
echo "本地提交 $SHA · 文件 $CNT · 体积 $SIZE"
log "commit $SHA files=$CNT size=$SIZE"

[ "$MODE" = "--push" ] || exit 0

# —— 3) 推送（token 从 600 权限文件读，绝不回显）——
[ -f "$ENVF" ] || { echo "⚠️ 缺少 $ENVF（含 GH_TOKEN），暂不推送"; log "no-token"; exit 0; }
# shellcheck disable=SC1090
. "$ENVF"
: "${GH_TOKEN:?}"
REMOTE=${GH_REMOTE:-origin}
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "⚠️ 未配置远端 $REMOTE，跳过推送"; log "no-remote"; exit 0
fi
if git -c credential.helper='!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f' push -q "$REMOTE" HEAD:main 2>>"$LOG"; then
  echo "✅ 已推送 $SHA → $REMOTE"
  log "pushed $SHA"
else
  echo "❌ 推送失败，详见 $LOG"; log "push-failed $SHA"; exit 1
fi
