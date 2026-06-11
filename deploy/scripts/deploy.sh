#!/usr/bin/env bash
# =============================================================================
# MediaRadar - one-shot deployment script
# =============================================================================
# Usage:
#   ./deploy.sh <DOMAIN> [--ssl] [--no-cache]
#
# Examples:
#   ./deploy.sh radar.example.com
#   ./deploy.sh radar.example.com --ssl
#   ./deploy.sh radar.example.com --no-cache
#
# Steps performed:
#   1. Sanity check (env, docker, nginx)
#   2. Sync nginx configs and substitute <DOMAIN>
#   3. (optional) Run ssl-init.sh to obtain Let's Encrypt cert
#   4. docker compose pull / build / up -d
#   5. Reload host nginx
#   6. Health check
# =============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

# ---------- pretty output ----------
readonly C_RESET=$'\033[0m'
readonly C_RED=$'\033[31m'
readonly C_GREEN=$'\033[32m'
readonly C_YELLOW=$'\033[33m'
readonly C_BLUE=$'\033[34m'
log()  { echo "${C_BLUE}[deploy]${C_RESET} $*"; }
ok()   { echo "${C_GREEN}[ ok ]${C_RESET} $*"; }
warn() { echo "${C_YELLOW}[warn]${C_RESET} $*" >&2; }
die()  { echo "${C_RED}[fail]${C_RESET} $*" >&2; exit 1; }

# ---------- arg parsing ----------
DOMAIN="${1:-}"
WITH_SSL="false"
NO_CACHE="false"
shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssl)      WITH_SSL="true"; shift ;;
        --no-cache) NO_CACHE="true"; shift ;;
        -h|--help)
            sed -n '2,16p' "$0"; exit 0 ;;
        *) die "Unknown argument: $1" ;;
    esac
done

[[ -z "$DOMAIN" ]] && die "Usage: $0 <DOMAIN> [--ssl] [--no-cache]"

# ---------- locate project root ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

log "Project root: $PROJECT_ROOT"
log "Target domain: $DOMAIN"

# ---------- preflight ----------
command -v docker    >/dev/null || die "docker not installed"
command -v docker-compose >/dev/null 2>&1 || true   # optional
docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin not installed"

[[ -f ".env" ]] || die ".env not found in project root. Copy .env.production.example to .env and fill in API keys first."

# Sanity-check .env has at least one LLM key
if ! grep -qE '^(DEFAULT_API_KEY|ANALYST_API_KEY|REVIEWER_API_KEY|EMBEDDING_API_KEY|VISION_API_KEY)=' .env; then
    warn ".env contains no LLM API keys - backend will start but LLM calls will fail"
fi

# ---------- sync nginx configs to /etc/nginx ----------
NGINX_AVAIL="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
NGINX_CONF_D="/etc/nginx/conf.d"
mkdir -p "$NGINX_AVAIL" "$NGINX_ENABLED" "$NGINX_CONF_D"

# Place main nginx.conf (only if missing or older - never clobber customisations)
if [[ ! -f /etc/nginx/nginx.conf ]] || [[ deploy/nginx/nginx.conf -nt /etc/nginx/nginx.conf ]]; then
    log "Installing host nginx.conf"
    cp deploy/nginx/nginx.conf /etc/nginx/nginx.conf
fi

# Install per-site config, with <DOMAIN> substitution
log "Installing mediaradar site config (domain=$DOMAIN)"
SED_DOMAIN="${DOMAIN//\//\\/}"
sed "s|__DOMAIN__|${SED_DOMAIN}|g" deploy/nginx/conf.d/mediaradar.conf \
    > "$NGINX_CONF_D/mediaradar.conf"

# Remove default site if present
rm -f "$NGINX_ENABLED/default"

# Validate nginx config
log "Validating nginx config (nginx -t)"
nginx -t

# ---------- SSL: fetch certs if missing ----------
LE_LIVE="/etc/letsencrypt/live/$DOMAIN"
if [[ "$WITH_SSL" == "true" ]] || [[ ! -f "$LE_LIVE/fullchain.pem" ]]; then
    if [[ -x deploy/scripts/ssl-init.sh ]]; then
        log "Running ssl-init.sh for $DOMAIN"
        deploy/scripts/ssl-init.sh "$DOMAIN"
    else
        warn "ssl-init.sh not found or not executable; assuming certs already at $LE_LIVE"
        [[ -f "$LE_LIVE/fullchain.pem" ]] || die "No SSL cert at $LE_LIVE - pass --ssl to fetch one"
    fi
else
    ok "Existing SSL cert found at $LE_LIVE"
fi

# ---------- docker compose up ----------
log "Pulling base images"
docker compose pull --ignore-pull-failures || true

log "Building & starting containers"
BUILD_FLAGS=(--build)
[[ "$NO_CACHE" == "true" ]] && BUILD_FLAGS+=(--no-cache)
docker compose up -d "${BUILD_FLAGS[@]}"

# ---------- wait for health ----------
log "Waiting for backend health"
for i in {1..30}; do
    if curl -fsS http://127.0.0.1:8000/openapi.json >/dev/null 2>&1; then
        ok "Backend healthy"
        break
    fi
    sleep 2
    [[ $i -eq 30 ]] && die "Backend failed to become healthy in 60s"
done

log "Waiting for Qdrant"
for i in {1..15}; do
    if curl -fsS http://127.0.0.1:6333/readyz >/dev/null 2>&1; then
        ok "Qdrant ready"
        break
    fi
    sleep 2
done

# ---------- reload host nginx ----------
log "Reloading host nginx"
systemctl reload nginx || nginx -s reload

# ---------- final summary ----------
ok "Deployment complete"
echo
echo "  Site URL :  https://${DOMAIN}"
echo "  API URL  :  https://${DOMAIN}/api/"
echo "  Docs     :  https://${DOMAIN}/docs"
echo
echo "  Useful commands:"
echo "    docker compose ps              # service status"
echo "    docker compose logs -f backend # tail backend logs"
echo "    docker compose logs -f qdrant  # tail Qdrant logs"
echo
