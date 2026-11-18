#!/bin/sh
# Start one player's box: create the user, hand them their files, run sshd.
# Safe to run again on every restart: a player's own work is never overwritten.
set -eu
: "${PLAYER:?}" "${PLAYER_HASH:?}"
case "$PLAYER" in *[!a-z0-9]*) echo "bad PLAYER" >&2; exit 1;; esac

home="/home/$PLAYER"
if ! id "$PLAYER" >/dev/null 2>&1; then
  useradd -M -d "$home" -s /bin/bash -u 1000 -U "$PLAYER"
fi
echo "$PLAYER:$PLAYER_HASH" | chpasswd -e
# the sshd of this box admits this player only
echo "AllowUsers $PLAYER" > /etc/ssh/sshd_config.d/allow.conf

mkdir -p "$home"
if [ ! -f "$home/.bashrc" ]; then
  cp -a /etc/skel/. "$home/"
  cat >> "$home/.bashrc" <<'RC'

# CTF box
export PS1='\[\e[1;33m\]\u\[\e[0m\]@ctf:\[\e[1;36m\]\w\[\e[0m\]\$ '
alias ll='ls -la'
cd ~ 2>/dev/null
RC
fi
# copy in challenge files that are not there yet (new challenges, or a fresh box)
mkdir -p "$home/challenges"
cp -rn /opt/challenges/. "$home/challenges/"
# the AI helper's key for this player, readable by them only
mkdir -p "$home/.ctf"
if [ -n "${AI_TOKEN:-}" ]; then
  printf '%s\n' "$AI_TOKEN" > "$home/.ctf/ai-token"
fi
mkdir -p /etc/ctf && printf '%s\n' "${SERVER_ADDR:-10.0.0.1}" > /etc/ctf/server
chown -R "$PLAYER:$PLAYER" "$home"
chmod 700 "$home" "$home/.ctf"
[ -f "$home/.ctf/ai-token" ] && chmod 600 "$home/.ctf/ai-token"

# this box's own host key, made on first start
ssh-keygen -A >/dev/null

/usr/local/sbin/motd.sh > /etc/motd
exec /usr/sbin/sshd -D -e
