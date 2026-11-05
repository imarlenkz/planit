#!/usr/bin/env bash
# Planit — one-command install / update on an Ubuntu/Debian VPS.
#
#   curl -fsSL https://raw.githubusercontent.com/imarlenkz/planit/main/deploy/install.sh \
#     | sudo DOMAIN=checker.imarlen.kz EMAIL=you@example.com bash
#
# Re-run the same command to update to the latest code (data, .env and certificates are kept).
# Options (env): DOMAIN (required), EMAIL (Let's Encrypt), BRANCH (default main), DIR (default /opt/planit),
#                DEMO (true = demo school + demo scan, for trials only; default false: any demo data is removed),
#                ADMIN_EMAIL (first administrator, created once when none exists; default $EMAIL),
#                MODE: standalone (Planit owns ports 80/443) | proxy (an nginx already runs on the host:
#                      Planit listens on 127.0.0.1:$PORT and a site for $DOMAIN is added to the host nginx).
#                      Default: proxy when port 80 is already taken, otherwise standalone.
#                PORT (proxy mode, default 8088)
#                IID_CLIENT_ID / IID_CLIENT_SECRET (+ IID_ISSUER, default https://id.imarlen.kz):
#                      enable "Sign in with iMARLEN ID"; written into .env, also on updates
#                USTAZ_INTEGRATION_KEY (+ USTAZ_API_URL): enable "Import from Ustaz"; the same key as
#                      PLANIT_INTEGRATION_KEY in Ustaz's .env
set -euo pipefail

DOMAIN="${DOMAIN:?set DOMAIN, e.g. DOMAIN=checker.imarlen.kz}"
EMAIL="${EMAIL:-admin@${DOMAIN#*.}}"
BRANCH="${BRANCH:-main}"
DIR="${DIR:-/opt/planit}"
DEMO="${DEMO:-false}"
ADMIN_EMAIL="${ADMIN_EMAIL:-$EMAIL}"
REPO="${REPO:-https://github.com/imarlenkz/planit.git}"
PORT="${PORT:-8088}"
if [ -z "${MODE:-}" ]; then
  if ss -ltn 2>/dev/null | grep -qE '[:.]80\s'; then MODE=proxy; else MODE=standalone; fi
fi

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
  sed -i -e "s|^SEED_DEMO=.*|SEED_DEMO=$DEMO|" -e "s|^DEMO_AUTORUN=.*|DEMO_AUTORUN=$DEMO|" .env
fi
# PUBLIC_URL is needed by the iMARLEN ID sign-in redirect
grep -q '^PUBLIC_URL=' .env || echo "PUBLIC_URL=" >> .env
grep -q '^PUBLIC_URL=.\+' .env || sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=https://$DOMAIN|" .env
setenv() { if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }
if [ -n "${IID_CLIENT_SECRET:-}" ]; then
  setenv IID_ISSUER "${IID_ISSUER:-https://id.imarlen.kz}"
  setenv IID_CLIENT_ID "${IID_CLIENT_ID:-planit}"
  setenv IID_CLIENT_SECRET "$IID_CLIENT_SECRET"
  echo "iMARLEN ID sign-in enabled (client ${IID_CLIENT_ID:-planit})"
fi
if [ -n "${USTAZ_INTEGRATION_KEY:-}" ]; then
  setenv USTAZ_API_URL "${USTAZ_API_URL:-https://ustaz.imarlen.kz/api}"
  setenv USTAZ_INTEGRATION_KEY "$USTAZ_INTEGRATION_KEY"
  echo "Ustaz student import enabled"
fi
# small servers: fewer processes so the stack fits next to other apps
MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$MEM_MB" -lt 6000 ] && ! grep -q '^PIPELINE_WORKERS=' .env; then
  sed -i -e "s|^API_WORKERS=.*|API_WORKERS=1|" -e "s|^WORKER_CONCURRENCY=.*|WORKER_CONCURRENCY=1|" .env
  echo "PIPELINE_WORKERS=2" >> .env
  echo "low memory (${MEM_MB} MB): 1 API worker, 1 Celery worker, 2 OCR threads"
fi

if [ "$MODE" = "proxy" ]; then
  log "4/6 Planit on 127.0.0.1:$PORT (host nginx stays in front)"
  sed -i -e "s|^HTTP_PORT=.*|HTTP_PORT=127.0.0.1:$PORT|" .env
  grep -q '^HTTP_PORT=' .env || echo "HTTP_PORT=127.0.0.1:$PORT" >> .env
  COMPOSE="docker compose -f docker-compose.yml"

  log "5/6 Host nginx site + HTTPS for $DOMAIN"
  if ss -ltn | grep -qE "127.0.0.1:$PORT\s" && ! docker ps --format '{{.Names}}' | grep -q '^planit-nginx'; then
    echo "port $PORT is already used on this server; re-run with another PORT=..."; exit 1
  fi
  OTHER=$(grep -rlE "server_name[^;]*\b$DOMAIN\b" /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null | grep -v "/$DOMAIN\$" || true)
  if [ -n "$OTHER" ]; then
    echo "$DOMAIN is already served by: $OTHER"
    echo "Remove or rename that server block first (or use another DOMAIN); nothing was changed in nginx."; exit 1
  fi
  command -v nginx >/dev/null || { echo "port 80 is busy but host nginx was not found. Free port 80 and re-run with MODE=standalone, or proxy https://$DOMAIN to 127.0.0.1:$PORT in your web server."; exit 1; }
  SITE=/etc/nginx/sites-available/$DOMAIN
  if [ ! -f "$SITE" ]; then
    cat > "$SITE" <<NGINX
# Planit ($DOMAIN) -> docker stack on 127.0.0.1:$PORT
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 200m;
    client_body_timeout 300s;

    location /api/ws/ {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
    }
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_request_buffering off;
        proxy_read_timeout 300s;
    }
}
NGINX
    ln -sf "$SITE" "/etc/nginx/sites-enabled/$DOMAIN"
  else
    echo "$SITE exists - kept"
  fi
  nginx -t && systemctl reload nginx
  if ! grep -q "ssl_certificate" "$SITE"; then
    command -v certbot >/dev/null || { apt-get update -y && apt-get install -y certbot python3-certbot-nginx; }
    certbot --nginx --non-interactive --agree-tos --redirect -m "$EMAIL" -d "$DOMAIN" \
      || { echo "Certificate failed: check that $DOMAIN has an A record pointing to this server."; exit 1; }
  else
    echo "HTTPS already configured for $DOMAIN"
  fi
else
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
fi

log "6/6 Build and start (the first build takes several minutes)"
$COMPOSE up -d --build --remove-orphans
# nginx resolves the backend/frontend containers once at start; recreated containers get new IPs (502 otherwise)
$COMPOSE restart nginx
echo "waiting for the API (first start also processes the demo scan)..."
for _ in $(seq 1 120); do
  if curl -fsS "https://$DOMAIN/api/health" >/dev/null 2>&1; then break; fi
  sleep 5
done
$COMPOSE ps
if [ "$DEMO" != "true" ]; then
  $COMPOSE exec -T backend python -m app.seed purge || true
  $COMPOSE exec -T backend python -m app.seed create-admin "$ADMIN_EMAIL" || true
fi
if curl -fsS "https://$DOMAIN/api/health"; then
  printf '\n\n\033[1;32mPlanit is running: https://%s\033[0m\n' "$DOMAIN"
  if [ "$DEMO" = "true" ]; then echo "Demo login: teacher@planit.kz / demo12345 (trial only)"; fi
else
  echo "API is not healthy yet. Logs: cd $DIR && $COMPOSE logs --tail 100 backend"
fi
