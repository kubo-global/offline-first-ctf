#!/usr/bin/env python3
"""
The AI helper: one small gateway between the players and an
open-weight model at an online provider (Together AI by default).

Why a gateway, and not the provider's key on a card:
  - the API key stays in this container; players never see it
  - each player has a cap per hour and the whole day has a token budget
  - the helper is a tutor: it explains and hints, the same for every player
  - every question is logged with who asked it, so usage can be checked

Players use it two ways, with the login on their card:
  - a chat page:           http://<server>:8083
  - the `ai` command in their box (it calls /v1/chat/completions, OpenAI-style)

Settings (environment):
  AI_API_KEY        the provider key. Empty: the helper says it is switched off.
  AI_BASE_URL       OpenAI-compatible base URL   (https://api.together.xyz/v1)
  AI_MODEL          model id                     (openai/gpt-oss-120b)
  AI_PER_HOUR       questions per player per hour (40)
  AI_MAX_TOKENS     longest answer, in tokens    (1500)
  AI_BUDGET_TOKENS  tokens for the whole event, questions and answers together (5000000)
  AI_MODE           tutor (explains and hints) or assistant (answers plainly)
  EVENT_NAME        what the helper calls the event  (Capture the Flag)
  FLAG_PREFIX       flags look like PREFIX{...}       (FLAG)
  AI_AUDIENCE       one sentence about the players, so it pitches its answers right
  AI_USERS          the players file from players.py   (/etc/aigate/users.json)
  AI_DATA           where the usage log is kept         (/data)

  python3 gate.py           run the gateway on port 8083
  python3 gate.py usage     who asked how much, from the log
"""
import hashlib, hmac, html, json, os, sys, threading, time, urllib.error, urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

E = os.environ.get
KEY = E("AI_API_KEY", "").strip()
BASE = E("AI_BASE_URL", "https://api.together.xyz/v1").rstrip("/")
MODEL = E("AI_MODEL", "openai/gpt-oss-120b")
PER_HOUR = int(E("AI_PER_HOUR", "40"))
MAX_TOKENS = int(E("AI_MAX_TOKENS", "1500"))
BUDGET = int(E("AI_BUDGET_TOKENS", "5000000"))
MODE = E("AI_MODE", "tutor")
EVENT = E("EVENT_NAME", "").strip() or "Capture the Flag"
FLAG = E("FLAG_PREFIX", "").strip() or "FLAG"
AUDIENCE = E("AI_AUDIENCE", "").strip() or ("Many of the players are new to security and some are new to "
                                            "the command line.")
USERS = E("AI_USERS", "/etc/aigate/users.json")
DATA = E("AI_DATA", "/data")
LOG = os.path.join(DATA, "usage.jsonl")
HERE = os.path.dirname(os.path.abspath(__file__))

MAX_MESSAGES = 16          # history kept per request, newest first
MAX_CHARS = 24000          # all messages together, so one paste cannot burn the budget

TOOLS = ("file, strings, xxd, base64, python3, exiftool, zbarimg, pngcheck, binwalk, zsteg, "
         "steghide, foremost, convert (ImageMagick), pdfinfo, tar, unzip, 7z, tshark, curl, sox, "
         "multimon-ng, ltrace, strace, gdb, objdump, and CyberChef in the browser")

COMMON = f"""You are the AI helper at a Capture the Flag event ({EVENT}).
{AUDIENCE} Flags look like {FLAG}{{...}}.

Every player has their own Linux box (Debian, bash) with these tools: {TOOLS}.
Their challenge files are in ~/challenges/<folder>/. There are tutorials on the event
site, and every challenge has hints on the game site.

Rules you always keep:
- Only help with the CTF challenges and with learning. Never help attack anything else:
  not other players' laptops, not the event network, not any real system or website.
- Keep answers short and in plain words. Put commands in code blocks.
- Answer in the language the player writes in."""

TUTOR = COMMON + """
- You are a tutor, not a solver. Explain the idea behind the challenge, suggest the next
  step or the tool to try, and ask what they already tried. Do not hand over a flag or a
  complete solution. If they are still stuck after trying your hint, give a stronger one.
- If someone pastes a flag and asks if it is right, tell them to submit it on the game site."""

ASSISTANT = COMMON + """
- Answer plainly and completely, and explain why it works so they learn from it."""

SYSTEM = TUTOR if MODE == "tutor" else ASSISTANT


# --- players ------------------------------------------------------------------------

def load_users():
    try:
        with open(USERS) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def check_password(rec, pw):
    salt, want = rec["pw"].split("$", 1)
    got = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return hmac.compare_digest(got, want)


# --- usage: caps per player and a budget for the day, rebuilt from the log on start ---

lock = threading.Lock()
recent = defaultdict(deque)   # login -> times of questions in the last hour
spent = defaultdict(int)      # login -> tokens
total = 0


def replay():
    global total
    if not os.path.exists(LOG):
        return
    cutoff = time.time() - 3600
    with open(LOG) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            spent[r["login"]] += r.get("tokens", 0); total += r.get("tokens", 0)
            if r["t"] > cutoff:
                recent[r["login"]].append(r["t"])


def allow(login):
    """None if this player may ask now, else the reason why not."""
    now = time.time()
    with lock:
        q = recent[login]
        while q and q[0] < now - 3600:
            q.popleft()
        if total >= BUDGET:
            return "The AI helper has used up its budget for today. Ask an organiser."
        if len(q) >= PER_HOUR:
            wait = int(q[0] + 3600 - now) // 60 + 1
            return f"You asked {PER_HOUR} questions this hour. Try again in {wait} min, or ask an organiser."
        q.append(now)
    return None


def record(login, level, source, usage, ok):
    global total
    tokens = int((usage or {}).get("total_tokens", 0))
    with lock:
        spent[login] += tokens; total += tokens
        os.makedirs(DATA, exist_ok=True)
        with open(LOG, "a") as fh:
            fh.write(json.dumps({"t": time.time(), "login": login, "level": level, "via": source,
                                 "tokens": tokens, "ok": ok}) + "\n")


def left(login):
    now = time.time()
    with lock:
        n = sum(1 for t in recent[login] if t > now - 3600)
    return {"per_hour": PER_HOUR, "left_this_hour": max(0, PER_HOUR - n), "model": MODEL,
            "mode": MODE, "on": bool(KEY)}


# --- the model ------------------------------------------------------------------------

def clean(messages):
    """Keep user and assistant turns only, newest last, within the size caps."""
    out, size = [], 0
    for m in reversed(messages if isinstance(messages, list) else []):
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        c = m.get("content")
        if not isinstance(c, str) or not c.strip():
            continue
        if size + len(c) > MAX_CHARS:
            if not out:   # the newest message alone is too long: keep its end
                out.append({"role": m["role"], "content": "[cut, too long]\n" + c[-MAX_CHARS:]})
            break
        out.append({"role": m["role"], "content": c}); size += len(c)
        if len(out) >= MAX_MESSAGES:
            break
    out.reverse()
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def ask_model(messages):
    body = json.dumps({"model": MODEL, "max_tokens": MAX_TOKENS, "temperature": 0.4,
                       "messages": [{"role": "system", "content": SYSTEM}] + messages}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body, method="POST", headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
        "User-Agent": "offline-first-ctf-aigate"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


# --- HTTP ------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "ctf-aigate"
    sys_version = ""

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def send_json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(b)

    def error(self, code, msg):
        # OpenAI-style, so the `ai` command and other clients can show it
        self.send_json(code, {"error": {"message": msg}})

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 200_000:
            return None
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return None

    def who(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        tok = auth[7:].strip().encode()
        for login, rec in self.server.users.items():
            if hmac.compare_digest(rec["token"].encode(), tok):
                return login, rec
        return None

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "chat.html"), "rb") as fh:
                b = fh.read().replace(b"__EVENT__", html.escape(EVENT).encode())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
        elif path == "/api/me":
            u = self.who()
            if not u:
                return self.error(401, "Log in with the login and password on your card.")
            self.send_json(200, {"login": u[0], "level": u[1]["level"], **left(u[0])})
        elif path == "/health":
            self.send_json(200, {"ok": True, "on": bool(KEY)})
        else:
            self.error(404, "not found")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        data = self.body()
        if data is None:
            return self.error(400, "Bad request.")
        if path == "/api/login":
            login = str(data.get("login", "")).strip().lower()
            rec = self.server.users.get(login)
            if not rec or not check_password(rec, str(data.get("password", ""))):
                time.sleep(1)
                return self.error(401, "That login and password do not match. Use the ones on your card.")
            # the chat page gets the same key the player's box has
            return self.send_json(200, {"login": login, "level": rec["level"], "token": rec["token"],
                                        **left(login)})
        if path in ("/v1/chat/completions", "/api/chat"):
            u = self.who()
            if not u:
                return self.error(401, "Log in with the login and password on your card.")
            login, rec = u
            if not KEY:
                return self.error(503, "The AI helper is switched off right now.")
            messages = clean(data.get("messages"))
            if not messages:
                return self.error(400, "Ask a question first.")
            why = allow(login)
            if why:
                return self.error(429, why)
            via = "web" if path == "/api/chat" else "box"
            try:
                out = ask_model(messages)
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode("utf-8", "replace")
                sys.stderr.write(f"upstream {e.code}: {detail}\n")
                record(login, rec["level"], via, None, False)
                return self.error(502, "The AI service did not answer. Try again in a minute.")
            except Exception as e:  # network down, timeout
                sys.stderr.write(f"upstream: {e!r}\n")
                record(login, rec["level"], via, None, False)
                return self.error(502, "The AI service cannot be reached. Try again in a minute.")
            record(login, rec["level"], via, out.get("usage"), True)
            msg = ((out.get("choices") or [{}])[0].get("message") or {})
            text = (msg.get("content") or "").strip() or "(no answer, try asking differently)"
            return self.send_json(200, {
                "object": "chat.completion", "model": MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                             "finish_reason": (out.get("choices") or [{}])[0].get("finish_reason")}],
                "usage": out.get("usage"), "quota": left(login)})
        self.error(404, "not found")


def usage_report():
    if not os.path.exists(LOG):
        return print("no questions yet")
    per = defaultdict(lambda: [0, 0, 0]); tot = 0
    with open(LOG) as fh:
        for line in fh:
            r = json.loads(line); p = per[r["login"]]
            p[0] += 1; p[1] += r.get("tokens", 0); p[2] += 0 if r.get("ok") else 1; tot += r.get("tokens", 0)
    print(f"{'login':10} {'questions':>9} {'tokens':>9} {'failed':>6}")
    for login in sorted(per):
        q, t, f = per[login]; print(f"{login:10} {q:9} {t:9} {f:6}")
    print(f"\n{sum(p[0] for p in per.values())} questions, {tot} tokens of {BUDGET} budget")


def main():
    if sys.argv[1:] == ["usage"]:
        return usage_report()
    users = load_users()
    srv = ThreadingHTTPServer(("0.0.0.0", 8083), Handler)
    srv.users = users   # login -> {level, pw (pbkdf2), token}
    replay()
    print(f"aigate: {len(users)} players, model {MODEL}, mode {MODE}, "
          f"{'key set' if KEY else 'NO KEY: helper is off'}, {total}/{BUDGET} tokens used", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
