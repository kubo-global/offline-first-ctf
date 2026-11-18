#!/bin/sh
# Ask for the login on the player's card, then SSH to their own box through sshpiper.
printf '\n  Capture the Flag: browser terminal\n\n  Login (from your card): '
read -r u
case "$u" in
  ''|*[!a-z0-9]*) printf '\n  Only the login from your card, lowercase letters and digits. Reload the page to try again.\n'; sleep 30; exit 1;;
esac
# one hop on the inside network, from this container to sshpiper; the player then logs in with their own password
exec ssh -p 2222 -o LogLevel=ERROR -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/tmp/known_hosts "$u@sshpiper"
