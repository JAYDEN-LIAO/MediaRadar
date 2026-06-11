#!/usr/bin/env bash
# =============================================================================
# MediaRadar - Let's Encrypt certificate bootstrap
# =============================================================================
# Usage:
#   ./ssl-init.sh <DOMAIN> [--staging] [--force]
#
# - Uses certbot in standalone mode on port 80.
# - Stops host nginx during issuance (certbot needs port 80).
# - Configures cert auto-renewal via a daily systemd timer.
#
# Requires: certbot installed on the host
#   apt-get install -y certbot
# =============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

readonly C_RESET=$'\033[0m'
readonly C_RED=$'\033[31m'
readonly C_GREEN=$'\033[32m'
readonly C_YELLOW=$'\033[33m'
readonly C_BLUE=$'\033[34m'
log()  { echo "${C_BLUE}[ssl]${C_RESET} $*"; }
ok()   { echo "${C_GREEN}[ ok ]${C_RESET} $*"; }
warn() { echo "${C_YELLOW}[warn]${C_RESET} $*" >&2; }
die()  { echo "${C_RED}[fail]${C_RESET} $*" >&2; exit 1; }

DOMAIN="${1:-}"
STAGING=""
FORCE="false"
shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --staging) STAGING="--staging"; shift ;;
        --force)   FORCE="true"; shift ;;
        -h|--help)
            sed -n '2,12p' "$0"; exit 0 ;;
        *) die "Unknown argument: $1" ;;
    esac
done

[[ -z "$DOMAIN" ]] && die "Usage: $0 <DOMAIN> [--staging] [--force]"
command -v certbot >/dev/null || die "certbot not installed - run: apt-get install -y certbot"

LE_LIVE="/etc/letsencrypt/live/$DOMAIN"
if [[ -f "$LE_LIVE/fullchain.pem" && "$FORCE" != "true" ]]; then
    ok "Cert already exists for $DOMAIN at $LE_LIVE (use --force to reissue)"
    exit 0
fi

# Stop nginx so certbot can bind :80
log "Stopping host nginx (certbot needs :80)"
systemctl stop nginx 2>/dev/null || nginx -s stop 2>/dev/null || true

EMAIL="${SSL_EMAIL:-admin@$DOMAIN}"
[[ -z "${SSL_EMAIL:-}" ]] && warn "SSL_EMAIL not set - using $EMAIL (change certbot register email after run if undesired)"

log "Requesting cert for $DOMAIN (staging=$STAGING force=$FORCE)"
certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --register-unsafely-without-email \
    --email "$EMAIL" \
    $STAGING \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

log "Restarting host nginx"
systemctl start nginx 2>/dev/null || nginx

# ---------- renewal: daily check via cron / systemd ----------
if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    log "Installing auto-renewal cron (daily 03:30)"
    ( crontab -l 2>/dev/null || true
      echo "30 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'"
    ) | crontab -
    ok "Renewal cron installed"
else
    ok "Renewal cron already present"
fi

# Also enable certbot timer if present (systemd)
if command -v systemctl >/dev/null && systemctl list-unit-files 2>/dev/null | grep -q certbot.timer; then
    systemctl enable --now certbot.timer >/dev/null 2>&1 && ok "certbot.timer enabled"
fi

ok "Cert installed at $LE_LIVE"
