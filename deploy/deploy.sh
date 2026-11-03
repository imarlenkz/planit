#!/bin/sh
# Server-side deploy: pull new images, run migrations, roll services. Run from the deploy directory with .env present.
set -eu
: "${IMAGE_PREFIX:?}" "${IMAGE_TAG:?}"
export IMAGE_PREFIX IMAGE_TAG
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
$COMPOSE pull backend worker beat frontend
$COMPOSE run --rm backend migrate
$COMPOSE up -d --remove-orphans
docker image prune -f >/dev/null
$COMPOSE ps
