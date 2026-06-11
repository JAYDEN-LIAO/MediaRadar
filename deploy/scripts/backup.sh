#!/usr/bin/env bash
# =============================================================================
# MediaRadar - data backup script
# =============================================================================
# Usage:
#   ./backup.sh                       # local backup only
#   ./backup.sh --s3                  # also push to S3 (uses BACKUP_S3_BUCKET)
#   BACKUP_KEEP_DAYS=14 ./backup.sh   # override retention
#
# Backs up:
#   - backend_data  (SQLite DBs: radar_state.db, agent_memory.db, etc.)
#   - backend_crawler_data (cookies, browser_data)
#   - qdrant_storage (vector snapshots, via qdrant CLI / volume tar)
#   - backend_logs (rotated, last 7d)
#
# Retention: keeps BACKUP_KEEP_DAYS (default 7) days of local archives.
# =============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

readonly C_RESET=$'\033[0m'
readonly C_RED=$'\033[31m'
readonly C_GREEN=$'\033[32m'
readonly C_YELLOW=$'\033[33m'
readonly C_BLUE=$'\033[34m'
log()  { echo "${C_BLUE}[backup]${C_RESET} $*"; }
ok()   { echo "${C_GREEN}[ ok ]${C_RESET} $*"; }
warn() { echo "${C_YELLOW}[warn]${C_RESET} $*" >&2; }
die()  { echo "${C_RED}[fail]${C_RESET} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

PUSH_S3="false"
[[ "${1:-}" == "--s3" ]] && PUSH_S3="true"

# ---------- config ----------
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="mediaradar_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_NAME"

mkdir -p "$BACKUP_DIR"

# ---------- preflight ----------
command -v docker >/dev/null || die "docker not installed"
command -v tar    >/dev/null || die "tar not installed"
command -v gzip   >/dev/null || die "gzip not installed"

# ---------- stage files ----------
STAGE="$(mktemp -d -t mediaradar-backup-XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT

log "Staging backup data -> $STAGE"

# 1. SQLite databases (from named volume)
log "  - backend_data"
docker run --rm \
    -v mediaradar_backend_data:/src:ro \
    -v "$STAGE":/dst \
    alpine:3.19 sh -c 'cp -a /src /dst/backend_data'

# 2. Crawler cookies / browser data
log "  - crawler_data"
docker run --rm \
    -v mediaradar_crawler_data:/src:ro \
    -v "$STAGE":/dst \
    alpine:3.19 sh -c 'cp -a /src /dst/backend_crawler_data'

# 3. Qdrant volume
log "  - qdrant_storage"
docker run --rm \
    -v mediaradar_qdrant:/src:ro \
    -v "$STAGE":/dst \
    alpine:3.19 sh -c 'cp -a /src /dst/qdrant_storage'

# 4. Logs (last 7d)
log "  - logs (rotated)"
docker run --rm \
    -v mediaradar_logs:/src:ro \
    -v "$STAGE":/dst \
    alpine:3.19 sh -c 'cp -a /src /dst/backend_logs'

# 5. Metadata
cat > "$STAGE/manifest.txt" <<EOF
MediaRadar backup
timestamp: $TIMESTAMP
host:      $(hostname -f 2>/dev/null || hostname)
backend_container: mediaradar-backend
qdrant_container:  mediaradar-qdrant
backend_image:     $(docker inspect mediaradar-backend --format '{{.Config.Image}}' 2>/dev/null || echo unknown)
qdrant_image:      $(docker inspect mediaradar-qdrant  --format '{{.Config.Image}}' 2>/dev/null || echo unknown)
git_commit:        $(git rev-parse HEAD 2>/dev/null || echo unknown)
EOF

# ---------- archive ----------
log "Compressing -> $ARCHIVE_PATH"
tar -czf "$ARCHIVE_PATH" -C "$STAGE" .

# Encrypt? if BACKUP_GPG_RECIPIENT set
if [[ -n "${BACKUP_GPG_RECIPIENT:-}" ]] && command -v gpg >/dev/null; then
    log "Encrypting with GPG for $BACKUP_GPG_RECIPIENT"
    gpg --batch --yes --trust-model always \
        -e -r "$BACKUP_GPG_RECIPIENT" \
        "$ARCHIVE_PATH"
    ARCHIVE_PATH="${ARCHIVE_PATH}.gpg"
fi

# Checksum
( cd "$BACKUP_DIR" && sha256sum "$(basename "$ARCHIVE_PATH")" > "$(basename "$ARCHIVE_PATH").sha256" )
ok "Local backup: $ARCHIVE_PATH"

# ---------- retention ----------
log "Pruning backups older than $BACKUP_KEEP_DAYS days"
find "$BACKUP_DIR" -maxdepth 1 -type f -name "mediaradar_*.tar.gz*" -mtime "+$BACKUP_KEEP_DAYS" -delete -print

# ---------- optional S3 push ----------
if [[ "$PUSH_S3" == "true" ]]; then
    : "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET must be set when using --s3}"
    if command -v aws >/dev/null; then
        log "Uploading to s3://$BACKUP_S3_BUCKET"
        aws s3 cp "$ARCHIVE_PATH" "s3://$BACKUP_S3_BUCKET/$ARCHIVE_NAME" \
            --storage-class STANDARD_IA
        ok "S3 upload complete"
    elif command -v rclone >/dev/null && [[ -n "${BACKUP_S3_REMOTE:-}" ]]; then
        log "Uploading via rclone to $BACKUP_S3_REMOTE:$BACKUP_S3_BUCKET"
        rclone copy "$ARCHIVE_PATH" "$BACKUP_S3_REMOTE:$BACKUP_S3_BUCKET/"
    else
        warn "No S3 tool (aws / rclone) found - skipping remote upload"
    fi
fi

ok "Backup complete"
