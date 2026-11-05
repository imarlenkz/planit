#!/usr/bin/env bash
# Planit — one-command install / update on an Ubuntu/Debian VPS.
#
#   curl -fsSL https://raw.githubusercontent.com/imarlenkz/planit/main/deploy/install.sh \
#     | sudo DOMAIN=checker.imarlen.kz EMAIL=you@example.com bash
#
# Re-run the same command to update to the latest code (data, .env and certificates are kept).
# Options (env): DOMAIN (required), EMAIL (Let's Encrypt), BRANCH (default main), DIR (default /opt/planit),
#                DEMO (true = demo school + demo scan on first start; default true)
set -euo pipefail

DOMAIN="${DOMAIN:?set DOMAIN, e.g. DOMAIN=checker.imarlen.kz}"
EMAIL="${EMAIL:-admin@${DOMAIN#*.}}"
BRANCH="${BRANCH:-main}"
DIR="${DIR:-/opt/planit}"
DEMO="${DEMO:-true}"
REPO="${REPO:-https://github.com/imarlenkz/planit.git}"

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)"; exit 1; }

log "1/6 Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true
docker compose version >/dev/null || { echo "docker compose plugin is missing"; exit 1; }
command -v git >/dev/null || { apt-get update -y && apt-get install -y git; }

log "2/6 Code ($BRANCH) -> $DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$DIR" checkout -B "$BRANCH" "origin/$BRANCH"
else
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$DIR"
fi
cd "$DIR"

log "3/6 Configuration (.env)"
if [ ! -f .env ]; then
  cp .env.example .env
  rand() { openssl rand -base64 64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
  sed -i \
    -e "s|^ENVIRONMENT=.*|ENVIRONMENT=production|" \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(rand 64)|" \
    -e "s|^FRONTEND_ORIGINS=.*|FRONTEND_ORIGINS=https://$DOMAIN|" \
    -e "s|^COOKIE_SECURE=.*|COOKIE_SECURE=true|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand 32)|" \
    -e "s|^STORAGE_ENCRYPTION_KEY=.*|STORAGE_ENCRYPTION_KEY=$(openssl rand -base64 32)|" \
    -e "s|^SEED_DEMO=.*|SEED_DEMO=$DEMO|" \
    -e "s|^DEMO_AUTORUN=.*|DEMO_AUTORUN=$DEMO|" \
    .env
  chmod 600 .env
  echo "created .env with generated secrets: $DIR/.env (add AI keys there later if needed)"
else
  echo ".env exists - kept"
fi

log "4/6 Nginx config for $DOMAIN"
sed -e "s|server_name _;|server_name $DOMAIN;|g" \
    -e "s|/etc/nginx/tls/fullchain.pem|/etc/letsencrypt/live/$DOMAIN/fullchain.pem|" \
    -e "s|/etc/nginx/tls/privkey.pem|/etc/letsencrypt/live/$DOMAIN/privkey.pem|" \
    nginx/prod.conf > nginx/server.conf
mkdir -p letsencrypt certbot-www

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.server.yml"

log "5/6 HTTPS certificate (Let's Encrypt)"
if [ ! -f "letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  $COMPOSE stop nginx >/dev/null 2>&1 || true
  docker run --rm -p 80:80 -v "$DIR/letsencrypt:/etc/letsencrypt" certbot/certbot:v2.11.0 \
    certonly --standalone --non-interactive --agree-tos -m "$EMAIL" -d "$DOMAIN" \
    || { echo "Certificate failed: check that $DOMAIN has an A record pointing to this server and port 80 is open."; exit 1; }
else
  echo "certificate exists - kept (renewed automatically by the certbot service)"
fi

log "6/6 Build and start (the first build takes several minutes)"
$COMPOSE up -d --build --remove-orphans
echo "waiting for the API..."
for _ in $(seq 1 120); do
  if curl -fsS "https://$DOMAIN/api/health" >/dev/null 2>&1; then break; fi
  sleep 5
done
$COMPOSE ps
if curl -fsS "https://$DOMAIN/api/health"; then
  printf '\n\n\033[1;32mPlanit is running: https://%s\033[0m\n' "$DOMAIN"
  if [ "$DEMO" = "true" ]; then echo "Demo login: teacher@planit.kz / demo12345 (set DEMO=false for real use)"; fi
else
  echo "API is not healthy yet. Logs: cd $DIR && $COMPOSE logs --tail 100 backend"
fi
