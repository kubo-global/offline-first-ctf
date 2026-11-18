#!/bin/sh
# The welcome text a player sees on login.
S="${SERVER_ADDR:-10.0.0.1}"
cat <<MOTD

  ${EVENT_NAME:-Capture the Flag}: your own box, everything pre-installed
  -----------------------------------------------------------
  You are $PLAYER, in the ${LEVEL:-} ranking.

  ~/challenges/   the files for every challenge, one folder each
  ctf-help        which tool for which kind of challenge
  ai "question"   ask the AI helper (hints, not flags)

  The game       http://$S:8000
  Tutorials      http://$S:8080
  CyberChef      http://$S:8080/cyberchef/
  AI helper      http://$S:8083

  Flags look like ${FLAG_PREFIX:-FLAG}{...}. Submit them on the game site.
  Copy a file to your laptop:  scp -P 2222 $PLAYER@$S:challenges/<folder>/<file> .

MOTD
