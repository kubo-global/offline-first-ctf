#!/usr/bin/env bash
# Build and pull everything, then save it to images.tar so the server can run the CTF
# with no internet. Run this with internet, on the server itself if you can (then the
# images match its processor without any extra step).
#
#   ./package-offline.sh                         # for this machine
#   PLATFORM=linux/arm64 ./package-offline.sh    # for a Mac with Apple chip or a Pi,
#                                                # built on an x86 machine (slower, emulated)
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "Copy .env.example to .env and set passwords first."; exit 1; }
[ -f docker-compose.players.yml ] || { echo "Run: python3 players.py --beginner N --experienced M   first."; exit 1; }

# the challenge pack, as set in .env
PACK=$(grep -E '^PACK=' .env | tail -1 | cut -d= -f2-); PACK=${PACK:-./example-pack}
[ -d "$PACK/files" ] || { echo "No challenge pack at $PACK (PACK in .env)."; exit 1; }

PULL=(ctfd/ctfd:3.8.9 mariadb:10.11 redis:7-alpine nginx:1.27-alpine farmer1992/sshpiperd:full-v1.6.1)
BUILT=(offline-first-ctf-playerbox:latest offline-first-ctf-webterm:latest offline-first-ctf-webchallenge:latest offline-first-ctf-aigate:latest)
CYBERCHEF_VERSION=v11.5.0

plat=()
[ -n "${PLATFORM:-}" ] && plat=(--platform "$PLATFORM")

echo "==> CyberChef $CYBERCHEF_VERSION (offline copy for the tutorials site)"
if [ ! -f cyberchef/index.html ]; then
  url=$(curl -fsSL "https://api.github.com/repos/gchq/CyberChef/releases/tags/$CYBERCHEF_VERSION" \
        | python3 -c 'import sys,json; print([a["browser_download_url"] for a in json.load(sys.stdin)["assets"] if a["name"].endswith(".zip")][0])')
  tmp=$(mktemp -d); curl -fsSL -o "$tmp/cc.zip" "$url"
  rm -rf cyberchef; mkdir cyberchef; (cd cyberchef && unzip -q "$tmp/cc.zip")
  mv cyberchef/CyberChef_*.html cyberchef/index.html; rm -rf "$tmp"
fi

echo "==> Building the player box, the browser terminal, the web challenge and the AI helper"
if [ -n "${PLATFORM:-}" ]; then
  docker buildx build ${plat[@]+"${plat[@]}"} --load -t offline-first-ctf-playerbox:latest --build-context pack="$PACK/files" playerbox
  docker buildx build ${plat[@]+"${plat[@]}"} --load -t offline-first-ctf-webterm:latest webterm
  docker buildx build ${plat[@]+"${plat[@]}"} --load -t offline-first-ctf-webchallenge:latest "$PACK/web-challenge"
  docker buildx build ${plat[@]+"${plat[@]}"} --load -t offline-first-ctf-aigate:latest aigate
else
  docker compose --profile build build playerbox webterm webchallenge aigate
fi

echo "==> Pulling the rest"
for i in "${PULL[@]}"; do docker pull ${plat[@]+"${plat[@]}"} "$i"; done

echo "==> Saving all images to images.tar"
docker save -o images.tar "${PULL[@]}" "${BUILT[@]}"

echo "==> Done. Copy this whole folder (with images.tar and players/) to the server."
ls -lh images.tar
