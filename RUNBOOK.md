# Runbook

One server in the room, no internet needed. This is everything to set up, run and
recover a Capture the Flag day with this kit. The addresses below use `192.168.0.10` for
the server; use your own.

## The server

Any machine with Docker and 8 GB of memory for it: a Linux laptop or mini-PC, a Raspberry
Pi 5 with 8 GB, or a Mac. On a Mac, install OrbStack (or Docker Desktop, or Colima) and
give its Linux VM 8 GB. On the day: mains power, sleep off, firewall on, everything else
closed.

The images are built for the server's processor (see First-time setup). Memory for about
60 players: 3 GB for the boxes (about 50 MB each when idle, capped at 384 MB), about 1.5 GB
for the rest.

### If the server is someone's own Mac

The players can never reach the Mac from their boxes: the box network has no route out,
and boxproxy only talks to the four CTF services. From their laptops on the Wi-Fi they can
reach whatever the Mac listens on, so:

- **A separate macOS user for the event**, for example `ctf`. Install OrbStack and
  keep the CTF folder there, and run the day logged in as that user. OrbStack's Linux VM
  can see the files of the user who runs it; with its own user that is only the CTF. No
  iCloud, mail or browser logins in that user.
- **System Settings > General > Sharing: everything off**: File Sharing, Screen Sharing,
  Remote Login, Remote Management, Media Sharing, Printer Sharing, AirPlay Receiver.
- **AirDrop: off** (or Contacts Only).
- **Firewall on**, with *stealth mode* on (Network > Firewall > Options). If macOS asks
  whether OrbStack may accept incoming connections, allow it: that is the CTF itself.
- **The hotspot password stays with you**, so the only network players are on is the
  CTF Wi-Fi.
- FileVault on, and the screen locks when you step away.
- Check at the rehearsal, from another laptop on the CTF Wi-Fi:
  `nc -zv 192.168.0.10 22 445 5900 5000 7000` should all fail, and the game should open.

## The network

Any home Wi-Fi router will do, with **nothing in its internet (WAN) port**: the
players' laptops get no internet from it.

The server has two connections, and they do different jobs (the settings shown are for
macOS; on Linux, set the same in your network manager):

- **Ethernet, to the router** (USB-C adapter into one of the four LAN ports): the room.
  Give it a fixed address by hand, with **no router**, so the server never sends its own
  internet traffic that way. System Settings > Network > the USB LAN adapter > Details >
  TCP/IP: Configure IPv4 *Manually*, IP address `192.168.0.10`, subnet mask
  `255.255.255.0`, Router *empty*. Then `SERVER_ADDR=192.168.0.10` in `.env`.
- **Wi-Fi, to the phone's hotspot**: internet for the AI helper only (see The AI helper).
  Without the AI helper, keep Wi-Fi off.
- Set `BIND_ADDR=192.168.0.10` too, so the CTF services listen on the room's network only
  and not on the hotspot. macOS *Internet Sharing* stays off: it would pass the hotspot on
  to every laptop in the room.

Setting up the router (once, at home, in a browser). These steps are for a TP-Link
Archer AX10; other routers have the same settings under other names:

1. Plug it in and connect to its Wi-Fi (name and password on the sticker underneath), or by
   cable. Open `http://tplinkwifi.net` (or `http://192.168.0.1`), choose an admin password.
2. Before the event, update its firmware: put a cable from your home router into its WAN
   port, then Advanced > System > Firmware Update. Unplug the WAN cable afterwards.
3. The quick setup asks how it connects to the internet: pick Dynamic IP and ignore the
   warning that there is no internet. Skip the TP-Link ID.
4. Wireless: a name such as `CTF`, WPA2/WPA3, a short password for the room (write it on the
   board). Same name on 2.4 and 5 GHz is fine.
5. Advanced > Network > DHCP Server: check the address pool (usually starts at
   `192.168.0.100`). `192.168.0.10` lies outside it, so it never goes to a laptop.
6. If it has *AP isolation* (wireless clients cannot see each other), turn it on, then
   check a laptop on the Wi-Fi still opens the game. If it does not, turn it off again.
7. Turn off WPS. Leave remote management off.

Players reach, from their own laptop:
- The game (CTFd): `http://192.168.0.10:8000`
- Their own box: `ssh -p 2222 <login>@192.168.0.10`
- The browser terminal, for laptops without ssh: `http://192.168.0.10:8082`
- Tutorials: `http://192.168.0.10:8080`, with CyberChef at `/cyberchef/`
- The web challenges: `http://192.168.0.10:8081`
- The AI helper: `http://192.168.0.10:8083`

Every player gets a **card** with their login and password and these addresses
(`players/cards.html`, print it; it holds every password, so keep it off shared drives). The same login works everywhere.

## The AI helper

An open-weight model (gpt-oss-120b at Together AI by default) that players can ask for
help, on a chat page and with the `ai` command in their box. It runs as a tutor: it
explains and gives hints, not flags, the same for every player.

- **Only the gateway goes online.** The key is in `.env` on the server and in the `aigate`
  container, nowhere else. The boxes sit on an internal network with no route out; their
  web tools go through `boxproxy`, which reaches only the game, the tutorials, the web
  challenges and the helper. The laptops have no internet at all.
- **Key:** make a Together AI key with a spending limit on the account, put it in `.env` as
  `AI_API_KEY`, then `docker compose up -d aigate`. Without a key the helper says it is
  switched off; everything else works.
- **Limits:** 40 questions per player per hour (`AI_PER_HOUR`), answers up to 1500 tokens,
  and 5 million tokens for the day (`AI_BUDGET_TOKENS`), questions and answers together.
  At gpt-oss-120b prices that is a few dollars at most; a normal day is far less.
- **Who asked how much:** `docker compose exec aigate python gate.py usage`
- **Plain answers instead of hints:** `AI_MODE=assistant` in `.env`, then `docker compose up -d aigate`.
- **Switch it off during the event:** `docker compose stop aigate` (or turn off the hotspot).
- Questions go to Together's servers. The chat page says so: no personal details in
  questions.

## The player boxes

Everyone brings their own laptop. Each player has their **own box**: a small Linux machine
in a container, everything pre-installed (`ctf-help` lists the tools by kind of challenge),
and the files of every challenge in `~/challenges/`. Everyone plays for themselves, in one
of two rankings in CTFd, **Beginner** and **Experienced**. Logins
are plain numbers (`player01`, `player02`, ...; the word comes from `LOGIN_PREFIX`); the ranking is on the card and fixed in CTFd. The scoreboard has a tab for each.

- Windows 10 and 11, macOS and Linux all have `ssh` built in. Anyone stuck uses the
  browser terminal: same login, same box.
- Copy a file to the laptop: `scp -P 2222 <login>@192.168.0.10:challenges/<folder>/<file> .`
- A box is capped in memory, CPU and processes, has no root and no sudo, and cannot open
  tunnels. Box files survive restarts.
- **Reset one player's box** (their files are kept): `docker compose up -d --force-recreate box-player07`
- **Wipe one player's box to the start:** `docker compose rm -sf box-player07 && docker volume rm offline-first-ctf_home-player07 && docker compose up -d box-player07`

## First-time setup (with internet, before the day)

1. In this folder:
   ```
   cp .env.example .env          # the event name, the passwords, SERVER_ADDR and PACK
   pip install requests          # the two setup scripts need it
   python3 players.py --beginner 15 --experienced 15   # logins, boxes, cards
   ./package-offline.sh          # builds + pulls everything, saves images.tar
   ```
   Run it on the server itself if you can. To build on an x86 machine for a Mac with Apple
   chip or a Pi, use `PLATFORM=linux/arm64 ./package-offline.sh`.
   More players later: run `players.py --beginner N --experienced M` again. Existing logins and
   passwords stay, so printed cards stay valid.
2. Keep the whole folder (with `images.tar` and `players/`) on the server and on a USB stick.

## On the server (no internet needed)

1. Load the images and start everything:
   ```
   docker load -i images.tar     # only on a fresh machine
   docker compose up -d
   ```
2. Wait a minute for the database, then set up CTFd and load the challenges:
   ```
   python3 provision.py
   python3 players.py --ctfd http://192.168.0.10:8000
   ```
   Both read `.env`. The first creates the admin, the pack's challenges with their hints
   and files, the Rules page and the theme, with the real address in every challenge
   text. The second creates every player
   in CTFd, in their ranking, with the password on their card. Registration on the game
   site is off: every account comes from a card.
3. Check: from a laptop on the Wi-Fi, log in to the game with a test card, `ssh` into the
   box, open the browser terminal, solve the warm-up, spend a hint, see the score move.
   With the AI helper: ask it something on the chat page and with `ai` in a box. Then, from a
   phone on the hotspot (not the CTF Wi-Fi), `http://<the server's hotspot address>:8000` must
   not open: that shows `BIND_ADDR` keeps the CTF off the hotspot.

## The day

- Open the doors an hour before the game starts: registration and Wi-Fi take that long.
- At registration, ask two questions: "Have you used a Linux terminal before?" and "Have
  you done a CTF or hacking challenge before?" Two yeses: a card from the Experienced pile
  (double border). Otherwise: a Beginner card. In doubt, Beginner.
- Opening: everyone plays alone; explaining is welcome, giving flags is not.
- Keep the printed address cards on the tables.

## If something breaks

- **A phone on the CTF Wi-Fi cannot open the game:** the Wi-Fi has no internet, so the
  phone keeps sending everything over mobile data. Turn mobile data off while on the CTF
  Wi-Fi, and answer "stay connected" when it warns about no internet. Laptops do not have
  this problem. The phone that runs the hotspot cannot do this, so test with another one.
- **A page keeps loading:** something on it is fetched from the internet. Every page the
  players see (game, tutorials, CyberChef, web challenges, AI helper, browser terminal)
  was checked to load nothing from outside; only the admin's text editor fetches a
  spelling list, and works without it.
- **CTFd is stuck or slow:** `docker compose restart ctfd`. Scores are safe in the
  database; nothing is lost.
- **The web challenges misbehave or a player broke something:**
  `docker compose restart webchallenge`. It holds no data, so this is always safe.
- **Nobody can SSH in:** `docker compose restart sshpiper`. One player cannot: reset their
  box (see The player boxes).
- **A full reset of the platform (keep data):** `docker compose down && docker compose up -d`.
- **The whole machine died:** on the backup machine, `docker load -i images.tar`,
  `docker compose up -d`, then the two provisioning commands. A few minutes, no internet
  needed. Scores start again from zero, so keep the server on mains power.
- **The AI helper answers that it cannot reach the service:** check the server's Wi-Fi is on
  the hotspot and the phone has signal, then `docker compose logs --tail 20 aigate`.
- **Nothing reaches the server:** check the network cable and that players are on the same
  Wi-Fi or switch, and that the server still has its fixed address.

## Safety

- The only service with a weakness is the web app, and it runs in its own container on the
  players network only, with no database and no path to anything else. The worst a player
  can do there is read a flag.
- The player boxes are ordinary shells, one per player, capped and without root. They
  cannot reach the database or the internet. They can reach each other's SSH (which needs that player's
  password) and anything a player starts listening on; that is the one shared surface, and
  the card says to attack only the challenges.
- The boxes have no solutions in them: the reversing programs are compiled inside the image
  and their sources removed (the build fails if one is left), and the flags and write-ups are
  never enter a build: only the pack's `files/` folder does.
- The database and cache sit on an internal Docker network with no route to the internet or
  the room.
- The room has no internet: the router has nothing in its WAN port. The server may have
  internet over the phone's hotspot for the AI helper, but only the `aigate` container
  uses it, and only to reach the model provider. The player boxes have no route out at
  all (internal network); `boxproxy` lets their web tools reach the room's services and
  nothing else.
- Flags, solutions and write-ups stay off any machine players can read, and out of any
  public place.
