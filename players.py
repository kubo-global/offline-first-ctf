#!/usr/bin/env python3
"""
Make the players for the day: one login, one box and one score per player, in two
rankings: Beginner and Experienced.

    python3 players.py --beginner 15 --experienced 15   # make (or extend) the player list
    python3 players.py --ctfd http://<server>:8000      # also create the accounts in CTFd

What it writes, all under players/ (git-ignored: it holds the passwords):
  players.csv                   login, level, password: the master list, kept between runs
  sshpiper/pipes.yaml           login -> that player's box, for the SSH router
  aigate/users.json             login -> password check and AI key, for the AI helper
and next to docker-compose.yml:
  docker-compose.players.yml    one service per player box, plus the volumes
and a printable sheet of cards: players/cards.html, the Beginner cards first, then the
Experienced ones, so they make two piles for the registration desk.

Logins are plain numbers, player01, player02, ... (LOGIN_PREFIX in .env): nobody can tell a player's level from their
login. The level is on the card and fixed with the login in CTFd, so a player cannot move
to the other ranking on the day. The same
login and password work for the SSH box, the browser terminal and the game site. Running it again keeps existing players
and their passwords and only adds new ones, so cards already printed stay valid.
"""
import argparse, csv, hashlib, html, json, os, re, secrets, sys
import kitenv

kitenv.load()
PREFIX = os.environ.get("LOGIN_PREFIX", "player")      # logins: player01, player02, ...
EVENT = os.environ.get("EVENT_NAME", "Capture the Flag")
FLAG = os.environ.get("FLAG_PREFIX", "FLAG")           # flags look like FLAG{...}
if not re.fullmatch(r"[a-z]+", PREFIX):
    sys.exit("LOGIN_PREFIX must be lowercase letters only")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "players")
CSV = os.path.join(OUT, "players.csv")

# short, friendly words that are easy to read off a card and type; no look-alikes
WORDS = """mango kora river baobab ferry market drum sabar yassa domoda wonjo afra benachin
attaya lantern harbour island palm sunset swallow pelican heron oyster cashew peanut tide
canoe garden rooftop bridge compass anchor beacon lighthouse signal pixel circuit cable
socket kernel packet router laptop keyboard mouse window shell script python puzzle cipher
riddle lock key vault flag ticket coral amber indigo copper silver violet orange lemon""".split()


def password():
    return "-".join(secrets.choice(WORDS) for _ in range(3)) + "-" + str(secrets.randbelow(90) + 10)


B64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
ORDER = [(0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4), (47, 5, 26), (6, 27, 48),
         (28, 49, 7), (50, 8, 29), (9, 30, 51), (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13),
         (56, 14, 35), (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19), (62, 20, 41)]


def sha512_crypt(pw, salt=None):
    """The $6$ hash the box sets with chpasswd -e (SHA-crypt, 5000 rounds), in plain Python,
    because macOS's openssl cannot make it and Python 3.13 dropped the crypt module."""
    p = pw.encode(); s = (salt or "".join(secrets.choice(B64) for _ in range(16))).encode()[:16]
    H = lambda *parts: hashlib.sha512(b"".join(parts)).digest()
    b = H(p, s, p)
    a = hashlib.sha512(p + s)
    n = len(p)
    a.update(b * (n // 64) + b[:n % 64])
    while n:
        a.update(b if n & 1 else p); n >>= 1
    c = a.digest()
    dp = H(p * len(p)); P = (dp * (len(p) // 64 + 1))[:len(p)]
    ds = H(s * (16 + c[0])); S = (ds * (len(s) // 64 + 1))[:len(s)]
    for i in range(5000):
        c = H(P if i & 1 else c, S if i % 3 else b"", P if i % 7 else b"", c if i & 1 else P)

    def enc(w, k):
        out = ""
        for _ in range(k):
            out += B64[w & 63]; w >>= 6
        return out
    tail = "".join(enc((c[x] << 16) | (c[y] << 8) | c[z], 4) for x, y, z in ORDER) + enc(c[63], 2)
    return f"$6${s.decode()}${tail}"


def load():
    if not os.path.exists(CSV):
        return []
    with open(CSV, newline="") as fh:
        return list(csv.DictReader(fh))


def save(rows):
    os.makedirs(OUT, exist_ok=True); os.chmod(OUT, 0o700)
    tmp = CSV + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["login", "level", "password", "hash", "ai_token"])
        w.writeheader(); w.writerows(rows)
    os.chmod(tmp, 0o600); os.replace(tmp, CSV)


LEVELS = {"beginner": "Beginner", "experienced": "Experienced"}


def extend(rows, counts):
    """Make sure each level has at least that many players; new ones get the next numbers."""
    nxt = max((int(r["login"][len(PREFIX):]) for r in rows), default=0) + 1
    for level, n in counts.items():
        for _ in range(n - sum(r["level"] == level for r in rows)):
            pw = password()
            rows.append({"login": f"{PREFIX}{nxt:02d}", "level": level, "password": pw, "hash": sha512_crypt(pw)})
            nxt += 1
    rows.sort(key=lambda r: r["login"])
    return rows


def with_ai_tokens(rows):
    # the key the player's box (and the chat page, after login) uses for the AI helper
    for r in rows:
        if not r.get("ai_token"):
            r["ai_token"] = secrets.token_urlsafe(24)
    return rows


def write_aigate(rows):
    # the gateway checks the card password itself (PBKDF2, the standard library has it)
    d = os.path.join(OUT, "aigate"); os.makedirs(d, exist_ok=True)
    old = {}
    p = os.path.join(d, "users.json")
    if os.path.exists(p):
        with open(p) as fh:
            old = json.load(fh)
    users = {}
    for r in rows:
        o = old.get(r["login"])
        if o and o.get("token") == r["ai_token"] and o.get("pwcheck") == hashlib.sha256(r["hash"].encode()).hexdigest():
            users[r["login"]] = o; continue   # unchanged: keep it, PBKDF2 is slow on purpose
        salt = secrets.token_bytes(16)
        h = hashlib.pbkdf2_hmac("sha256", r["password"].encode(), salt, 200_000).hex()
        users[r["login"]] = {"level": r["level"], "pw": f"{salt.hex()}${h}", "token": r["ai_token"],
                             "pwcheck": hashlib.sha256(r["hash"].encode()).hexdigest()}
    with open(p + ".tmp", "w") as fh:
        json.dump(users, fh, indent=1)
    # read by the gateway's own user inside its container, so not 600; the folder is 700
    os.chmod(p + ".tmp", 0o644); os.replace(p + ".tmp", p)


def write_pipes(rows):
    # No known_hosts for the boxes: each box makes its own host key, and the hop from
    # sshpiper to a box runs on the inside Docker network, where the boxes cannot spoof
    # traffic (they have no NET_RAW capability). Players check sshpiper's own key.
    d = os.path.join(OUT, "sshpiper"); os.makedirs(d, exist_ok=True)
    lines = ['# generated by players.py: login -> that player\'s own box', 'version: "1.0"', "pipes:"]
    for r in rows:
        lines += [f'- from:', f'    - username: "{r["login"]}"', f"  to:",
                  f'    host: box-{r["login"]}:22', f'    username: "{r["login"]}"']
    p = os.path.join(d, "pipes.yaml")
    with open(p, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(p, 0o644)


def write_compose(rows):
    lines = ["# generated by players.py: one box per player. Do not edit, run players.py again.",
             "x-box: &box",
             "  image: offline-first-ctf-playerbox:latest",
             "  restart: unless-stopped",
             "  hostname: ctf",
             "  networks: [boxes]",
             "  # one player cannot slow the room down: memory, CPU and process caps",
             "  mem_limit: 384m",
             "  cpus: 0.5",
             "  pids_limit: 200",
             "  # no root powers beyond what sshd needs to log a player in",
             "  cap_drop: [ALL]",
             "  cap_add: [CHOWN, DAC_OVERRIDE, FOWNER, SETUID, SETGID, SYS_CHROOT, AUDIT_WRITE, KILL, NET_BIND_SERVICE]",
             "  security_opt: [\"no-new-privileges:true\"]",
             "", "services:"]
    for r in rows:
        h = r["hash"].replace("$", "$$")  # compose would read $ as a variable
        lines += [f"  box-{r['login']}:", "    <<: *box",
                  "    environment:",
                  f"      - PLAYER={r['login']}", f"      - LEVEL={LEVELS[r['level']]}",
                  f"      - PLAYER_HASH={h}", f"      - AI_TOKEN={r['ai_token']}",
                  "      - SERVER_ADDR=${SERVER_ADDR:-10.0.0.1}",
                  "      - EVENT_NAME=${EVENT_NAME:-Capture the Flag}",
                  "      - FLAG_PREFIX=${FLAG_PREFIX:-FLAG}",
                  "    volumes:",
                  f"      - home-{r['login']}:/home/{r['login']}"]
    lines += ["", "volumes:"]
    lines += [f"  home-{r['login']}:" for r in rows]
    with open(os.path.join(HERE, "docker-compose.players.yml"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_cards(rows, server):
    """Printable cards, 8 per A4 page, Beginner pile first. The look follows the event's
    certificate: KUBO yellow, Roboto Mono, the swallows and the sudo ./learn keycap. White
    paper, so a full sheet does not empty the printer; the art is embedded, so the file
    works offline."""
    import base64

    def art(name, mime):
        with open(os.path.join(HERE, "cards", name), "rb") as fh:
            return f"data:{mime};base64," + base64.b64encode(fh.read()).decode()
    # no web font: the server has no internet on the day, and the page would hang on it
    css = """@page{size:A4;margin:8mm}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:#262323;font-family:'Roboto Mono',ui-monospace,Menlo,monospace;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
.sheet{display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:68mm;gap:0;width:194mm;margin:0 auto}
.card{position:relative;overflow:hidden;border:0.3mm dashed #b9b3a6;padding:5mm 6mm 4mm;break-inside:avoid}
.card::before{content:"";position:absolute;right:5mm;top:4.2mm;width:13mm;height:11mm;
  background:url(SWALLOWS) right top/contain no-repeat}
.card::after{content:"";position:absolute;right:-2mm;bottom:-3mm;width:26mm;height:23mm;
  background:url(KEYCAP) center/contain no-repeat;transform:rotate(-8deg);opacity:.95}
.top{display:flex;align-items:center;gap:3mm;font-size:6.6pt;letter-spacing:.14em;text-transform:uppercase;font-weight:500}
.tag{border:0.35mm solid #262323;padding:.5mm 2mm;font-weight:700;letter-spacing:.12em}
.experienced .tag{background:#f9bf2a;border-color:#f9bf2a}
h2{margin:2mm 0 2.2mm;font-size:15pt;line-height:1;font-weight:700;letter-spacing:-.01em;text-transform:uppercase}
h2 span{color:#f9bf2a}
.cred{border-top:0.35mm solid #262323;border-bottom:0.35mm solid #262323;padding:1.2mm 0;margin-bottom:2mm;width:74mm}
.row{display:flex;justify-content:space-between;align-items:baseline;margin:.6mm 0;font-size:7pt;text-transform:uppercase;letter-spacing:.1em}
.row b{font-size:10.5pt;letter-spacing:0;text-transform:none;white-space:nowrap}
.how{font-size:6.7pt;line-height:1.5;width:64mm}
.how code{font-weight:700;font-family:inherit}
.how .k{display:inline-block;width:19mm;color:#6d6863;text-transform:uppercase;letter-spacing:.08em;font-size:6pt}
.foot{margin-top:1.6mm;font-size:5.6pt;letter-spacing:.2em;text-transform:uppercase;color:#6d6863}
.rule{font-size:6.3pt;margin-top:1.2mm;font-weight:500}
@media screen{body{background:#f4f0e3;padding:10mm 0}.sheet{background:#fff;box-shadow:0 1mm 6mm rgba(0,0,0,.12)}}
""".replace("SWALLOWS", art("swallows.png", "image/png")).replace("KEYCAP", art("keycap.webp", "image/webp"))
    cards = []
    for r in sorted(rows, key=lambda r: (r["level"] != "beginner", r["login"])):
        L = html.escape(r["login"]); P = html.escape(r["password"]); S = html.escape(server)
        cards.append(f"""<div class="card {r['level']}">
<div class="top"><span>{html.escape(EVENT)}</span><span class="tag">{LEVELS[r['level']]}</span></div>
<h2>Capture the <span>Flag</span></h2>
<div class="cred"><div class="row"><span>Login</span><b>{L}</b></div><div class="row"><span>Password</span><b>{P}</b></div></div>
<div class="how"><span class="k">Game</span><code>http://{S}:8000</code><br>
<span class="k">Your box</span><code>ssh -p 2222 {L}@{S}</code><br>
<span class="k">No ssh?</span><code>http://{S}:8082</code><br>
<span class="k">Tutorials</span><code>http://{S}:8080</code><br>
<span class="k">AI helper</span><code>http://{S}:8083</code> or <code>ai</code><br>
<div class="rule">Flags look like {html.escape(FLAG)}{{...}}. Attack only the challenges.</div></div>
<div class="foot">Learn &nbsp;Practice &nbsp;Capture &nbsp;Grow</div></div>""")
    with open(os.path.join(OUT, "cards.html"), "w") as fh:
        fh.write(f"<!doctype html><meta charset=utf-8><title>Player cards</title><style>{css}</style>"
                 f"<div class=sheet>{''.join(cards)}</div>\n")
    os.chmod(os.path.join(OUT, "cards.html"), 0o600)  # it holds every password


def ctfd(rows, base, admin_name, admin_pw):
    """Create each player in CTFd, with the same login and password, in their ranking
    (a CTFd bracket). Idempotent."""
    import requests
    s = requests.Session()
    r = s.get(f"{base}/login"); nonce = re.search(r'name="nonce"[^>]*value="([a-f0-9]+)"', r.text).group(1)
    s.post(f"{base}/login", data={"name": admin_name, "password": admin_pw, "nonce": nonce, "_submit": "Submit"})
    r = s.get(f"{base}/admin/config"); m = re.search(r"'csrfNonce':\s*\"([a-f0-9]+)\"", r.text)
    if not m:
        sys.exit("could not log in to CTFd as admin")
    s.headers["CSRF-Token"] = m.group(1)

    def all_of(kind):
        out, page = {}, 1
        while True:
            j = s.get(f"{base}/api/v1/{kind}", params={"page": page, "view": "admin"}).json()
            out.update({x["name"]: x["id"] for x in j["data"]})
            if not j.get("meta", {}).get("pagination", {}).get("next"):
                return out
            page += 1

    brackets = {b["name"]: b["id"] for b in s.get(f"{base}/api/v1/brackets").json()["data"]}
    for name in LEVELS.values():
        if name not in brackets:
            j = s.post(f"{base}/api/v1/brackets", json={"name": name, "type": "users",
                       "description": f"The {name} ranking"}).json()
            brackets[name] = j["data"]["id"]; print("ranking", name)
    users = all_of("users")
    for r in rows:
        bid = brackets[LEVELS[r["level"]]]
        if r["login"] not in users:
            j = s.post(f"{base}/api/v1/users", json={"name": r["login"], "email": f"{r['login']}@ctf.local",
                                                     "password": r["password"], "verified": True,
                                                     "bracket_id": bid}).json()
            if not j.get("success"):
                print("!!", r["login"], j); continue
            users[r["login"]] = j["data"]["id"]; print("user", r["login"])
        else:
            s.patch(f"{base}/api/v1/users/{users[r['login']]}", json={"bracket_id": bid})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--beginner", type=int, default=0, help="make sure there are N beginner players")
    ap.add_argument("--experienced", type=int, default=0, help="make sure there are N experienced players")
    ap.add_argument("--server", default=os.environ.get("SERVER_ADDR", "10.0.0.1"), help="address on the cards")
    ap.add_argument("--ctfd", help="CTFd base URL: also create the accounts there")
    ap.add_argument("--admin", default="admin"); ap.add_argument("--admin-password", default=os.environ.get("CTFD_ADMIN_PASSWORD"))
    a = ap.parse_args()
    rows = extend(load(), {"beginner": a.beginner, "experienced": a.experienced})
    if not rows:
        sys.exit("no players yet: pass --beginner N --experienced M")
    if any(r.get("level") not in LEVELS or not re.fullmatch(re.escape(PREFIX) + r"\d+", r["login"]) for r in rows):
        sys.exit(f"players/players.csv has logins that do not start with {PREFIX!r} (LOGIN_PREFIX): "
                 "move it away and run again")
    rows = with_ai_tokens(rows)
    save(rows)
    write_aigate(rows); write_pipes(rows); write_compose(rows); write_cards(rows, a.server)
    n = {lv: sum(r["level"] == lv for r in rows) for lv in LEVELS}
    print(f"{len(rows)} players: {n['beginner']} beginner, {n['experienced']} experienced; cards for {a.server}")
    if a.ctfd:
        if not a.admin_password:
            sys.exit("set CTFD_ADMIN_PASSWORD (or --admin-password) to create the CTFd accounts")
        ctfd(rows, a.ctfd.rstrip("/"), a.admin, a.admin_password)


if __name__ == "__main__":
    main()
