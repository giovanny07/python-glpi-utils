#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Giovanny Rodriguez, Imagunet
#
# Prepare a fresh glpi/glpi container for the integration tests:
# wait for the auto-install, enable the APIs, open the default legacy API
# client to any IP, and (GLPI 11+) create an OAuth client.
# Prints "export GLPI_IT_*=..." lines on stdout.
#
# Usage: glpi_it_setup.sh <glpi_container> <db_container> <base_url>
# Env:   DOCKER (default: docker; use podman locally)
set -euo pipefail

GLPI=$1 DB=$2 URL=$3
DOCKER=${DOCKER:-docker}
HERE=$(cd "$(dirname "$0")" && pwd)
console() { $DOCKER exec -u www-data -w /var/www/glpi "$GLPI" php bin/console "$@"; }

# The image installs GLPI on first start; console commands fail until done.
for _ in $(seq 1 120); do
    if console config:set enable_api 1 >/dev/null 2>&1 \
        || console glpi:config:set enable_api 1 >/dev/null 2>&1; then
        break
    fi
    sleep 5
done
version=$($DOCKER exec "$DB" mariadb -uglpi -pglpi glpi -N -e \
    "SELECT value FROM glpi_configs WHERE context='core' AND name='version'")
[ -n "$version" ] || { echo "GLPI did not finish installing" >&2; exit 1; }
major=${version%%.*}

for key in enable_api_login_credentials enable_api_login_external_token enable_hlapi; do
    console config:set "$key" 1 >/dev/null 2>&1 || console glpi:config:set "$key" 1 >/dev/null 2>&1 || true
done
# The default API client only accepts 127.0.0.1; tests reach it via the bridge IP.
$DOCKER exec "$DB" mariadb -uglpi -pglpi glpi -e \
    "UPDATE glpi_apiclients SET ipv4_range_start=NULL, ipv4_range_end=NULL WHERE id=1"

# Wait until the legacy API answers a login.
for _ in $(seq 1 60); do
    curl -sf -u glpi:glpi "$URL/apirest.php/initSession" >/dev/null && break
    sleep 2
done

echo "export GLPI_IT_URL=$URL"
echo "export GLPI_IT_VERSION=$version"
if [ "$major" -ge 11 ]; then
    $DOCKER cp "$HERE/glpi_oauth_client.php" "$GLPI:/tmp/glpi_oauth_client.php"
    read -r cid secret < <($DOCKER exec -u www-data -w /var/www/glpi "$GLPI" php /tmp/glpi_oauth_client.php | tail -1)
    echo "export GLPI_IT_CLIENT_ID=$cid"
    echo "export GLPI_IT_CLIENT_SECRET=$secret"
fi
