# Notes for an AI assistant adapting this kit

You are helping someone run a Capture the Flag day with this kit, on their own machine and
for their own room. This file tells you how the kit is built, what must stay true when you
change it, and how to prove a change works. Read `README.md` and `RUNBOOK.md` first.

## Start by asking

The kit ran once, on a Mac with a home router and a phone hotspot. The person in front of
you has something else. Before you change anything, find out:

- What is the server? (Linux, macOS, Windows with WSL, a Raspberry Pi; how much memory)
- How many players, and do they bring laptops, phones or both?
- Is there any internet in the room? Is the AI helper wanted?
- Do they have challenges, or do they start from the example pack or the 30-challenge pack?
- Individual play in two rankings (as built), one ranking, or teams?

## The map

| Path | What it does |
|---|---|
| `docker-compose.yml` | Every service and the three networks |
| `.env.example` | Every setting, explained. The real `.env` is never committed |
| `kitenv.py` | Reads `.env` for the Python scripts |
| `players.py` | Logins, one box per player (`docker-compose.players.yml`), cards, CTFd accounts |
| `provision.py` | Loads a pack into CTFd through its API |
| `package-offline.sh` | Builds, pulls and saves all images to `images.tar` |
| `playerbox/` | The image of a player's Linux box, and the `ai` and `ctf-help` commands |
| `webterm/` | The browser terminal (ttyd, then SSH to the box) |
| `aigate/` | `gate.py`, the AI helper gateway, and `boxproxy.py`, the boxes' only way out |
| `nginx/guides.conf` | The guides site: the pack's tutorials, and CyberChef at `/cyberchef/` |
| `themes/kubo/` | The CTFd theme |
| `example-pack/` | A small challenge pack; its `catalog.py` documents the format |

## What must stay true

These are the reasons the kit works in a closed room. A change that breaks one of them is
a regression, even if everything still starts.

1. **Nothing a player sees is fetched from outside.** No web fonts, no CDN scripts, no
   remote images, in the theme, the guides, the cards, the chat page or a challenge.
2. **Flags never enter a container image.** `catalog.py` and write-ups are read on the
   organiser's machine only. Only the pack's `files/` folder is a build context, and `.c`
   sources are deleted in the build after compiling.
3. **A player box has no route out.** The `boxes` network is `internal: true`. The only
   exit is `boxproxy`, with a fixed list of the room's own services. Do not add hosts to
   that list that are outside the room.
4. **The database is reachable by CTFd only.** `ctfd_internal` stays internal and the
   database publishes no port.
5. **Only `aigate` talks to the internet**, and only to the model provider. The provider
   key lives in `.env` and that container. It never goes into a box, a card or a page.
6. **The AI helper keeps its limits**: per player per hour, per answer, and a budget for
   the day. In tutor mode it does not get the flags, in its instructions or anywhere else.
7. **One login per player, from a card.** Registration on the game site stays off.
8. **Everything needed on the day is in `images.tar` and the folder.** If you add an image
   or a download, add it to `package-offline.sh` too.
9. **Scripts are safe to run twice.** `players.py` keeps existing logins and passwords;
   `provision.py` updates what is already there.
10. **Passwords stay out of git and out of your output.** `players/`, `.env` and
    `docker-compose.players.yml` are ignored. Do not print `players.csv` or `cards.html`.

## Common adaptations

- **Another server.** The runbook's network steps are written for macOS. On Linux, give
  the wired interface a fixed address with no gateway. `SERVER_ADDR` is that address, and
  `BIND_ADDR` the same if the server has a second network.
- **Another processor.** Run `package-offline.sh` on the server itself. Building for
  another processor with `PLATFORM=` has not been tried in this version; test it.
- **No AI helper.** Leave `AI_API_KEY` empty. Nothing else changes.
- **Another model provider.** Set `AI_BASE_URL` and `AI_MODEL` to any OpenAI-compatible
  service. For a model on the server itself, the gateway must reach it by a name on the
  `players` network; that set-up has not been tried.
- **Another event shape.** The tutor's instructions are `COMMON`, `TUTOR` and `ASSISTANT`
  in `aigate/gate.py`. The tools it mentions are `TOOLS`, and must match what
  `playerbox/Dockerfile` installs and what `playerbox/ctf-help` lists.
- **Challenges that are built, not found** (for example a day about building with AI). A
  challenge still needs a finish a machine can check. One way: a small checking service in
  the pack's `web-challenge/` that runs the player's work and returns a flag when it
  passes. This has not been done with the kit; treat it as new work.
- **Teams, or one ranking.** The two levels are `LEVELS` in `players.py`, and CTFd runs in
  `user_mode: users` (set in `provision.py`). Both must change together.
- **Another look.** Copy `themes/kubo/` under a new name, mount it in
  `docker-compose.yml`, and set `CTFD_THEME`. Keep fonts inside the theme.

## Prove it works

Do not report a change as done until you have run this, with `BIND_ADDR=127.0.0.1` and a
`SERVER_ADDR` that is not `127.0.0.1`:

```
python3 players.py --beginner 1 --experienced 1
docker compose --profile build build playerbox webterm webchallenge aigate
docker compose up -d
CTFD_URL=http://127.0.0.1:8000 python3 provision.py
python3 players.py --ctfd http://127.0.0.1:8000
```

Then check, as a player from `players/players.csv`:

- Log in on the game site; the event name and tagline show; a correct flag scores.
- `ssh -p 2222 <login>@127.0.0.1` reaches that player's box; `~/challenges/` has the files.
- From inside a box, `curl http://<SERVER_ADDR>:8000/login` answers 200 and
  `curl http://example.com` is refused.
- Ports 8080, 8081, 8082 and 8083 answer.
- No page lists a resource (script, stylesheet, font, image) from another host.
- With the AI helper on: `ai "hello"` answers in a box, and the hourly limit holds.

Say plainly what you ran and what you could not run. A rehearsal in the real room, on the
real network, is the last test, and only the organiser can do it.
