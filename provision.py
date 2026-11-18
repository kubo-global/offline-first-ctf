#!/usr/bin/env python3
"""
Set up a running CTFd from a challenge pack: the admin account, the challenges with
their flags, hints, tags and files, the Rules page and the theme.

    python3 provision.py

It reads .env (see .env.example): CTFD_ADMIN_PASSWORD, SERVER_ADDR, PACK, EVENT_NAME,
EVENT_TAGLINE. CTFD_URL defaults to http://<SERVER_ADDR>:8000.

Safe to run again: a challenge that is already there (same name) only gets its texts
updated, so it can be rerun after the server address changed.
"""
import re, sys, os, time
import kitenv

kitenv.load()
import requests

PACK = kitenv.pack()
sys.path.insert(0, PACK)
import catalog                                   # the pack's challenge list
CHALLENGES = catalog.CHALLENGES
RULES = getattr(catalog, "RULES", None)

E = os.environ.get
BASE = E("CTFD_URL") or f"http://{E('SERVER_ADDR', '127.0.0.1')}:8000"
if not E("CTFD_ADMIN_PASSWORD"):
    sys.exit("Set CTFD_ADMIN_PASSWORD (in .env or the environment): the password of the CTFd admin.")
ADMIN = {"name": "admin", "email": "admin@ctf.local", "password": E("CTFD_ADMIN_PASSWORD")}
EVENT = E("EVENT_NAME") or "Capture the Flag"
TAGLINE = E("EVENT_TAGLINE") or ""
THEME = E("CTFD_THEME") or "kubo"
FILES = os.path.join(PACK, "files")
s = requests.Session(); s.headers["Connection"] = "close"


def nonce_form(html):
    m = re.search(r'name="nonce"[^>]*value="([a-f0-9]+)"', html); return m.group(1) if m else None
def nonce_js(html):
    m = re.search(r"'csrfNonce':\s*\"([a-f0-9]+)\"", html); return m.group(1) if m else None


def setup():
    r = s.get(f"{BASE}/setup")
    nonce = nonce_form(r.text)
    if nonce is None:
        # set up before: log in as the admin instead
        r = s.get(f"{BASE}/login")
        s.post(f"{BASE}/login", data={"name": ADMIN["name"], "password": ADMIN["password"],
                                      "nonce": nonce_form(r.text), "_submit": "Submit"})
        print("already set up, logged in as admin"); return
    data = {"name": ADMIN["name"], "email": ADMIN["email"], "password": ADMIN["password"],
            "ctf_name": EVENT,
            "ctf_description": TAGLINE,
            "user_mode": "users",
            "challenge_visibility": "private", "account_visibility": "public",
            "registration_visibility": "private", "score_visibility": "public",
            "verify_emails": "false", "ctf_theme": "core", "theme_color": "#ffcd31",
            "start": "", "end": "", "social_shares": "true", "nonce": nonce, "_submit": "Finish"}
    r = s.post(f"{BASE}/setup", data=data); print("setup ->", r.status_code)


def csrf():
    r = s.get(f"{BASE}/admin/config"); n = nonce_js(r.text)
    if not n: print("!! not logged in", r.status_code, r.url); sys.exit(1)
    return n


def api(method, path, token, **kw):
    for _ in range(4):
        h = dict(kw.pop("headers", {})); h["CSRF-Token"] = token
        r = s.request(method, f"{BASE}{path}", headers=h, **kw)
        if r.text.strip():
            return r
        time.sleep(0.3)
    return r


def create():
    """Create the challenges; a challenge that is already there (same name) only gets its
    texts updated, so running this again after the address changed is safe."""
    token = csrf()
    have = {x["name"]: x["id"] for x in api("GET", "/api/v1/challenges", token, params={"view": "admin"}).json()["data"]}
    by_cat, updated = {}, 0
    for c in CHALLENGES:
        desc = c["desc"]
        if c.get("files"):
            # the same files are already in every player's box
            desc += f"\n\nAlso in your box: ~/challenges/{c['slug']}/"
        body = {"name": c["name"], "category": c["category"], "description": desc,
                "value": c["value"], "state": "visible", "type": "standard"}
        if c.get("connection_info"):
            body["connection_info"] = c["connection_info"]
        if c["name"] in have:
            r = api("PATCH", f"/api/v1/challenges/{have[c['name']]}", token,
                    json={k: body[k] for k in ("description", "connection_info") if k in body})
            if r.status_code >= 400:
                print("!! update", c["slug"], r.status_code, r.text[:160])
            updated += 1; continue
        r = api("POST", "/api/v1/challenges", token, json=body)
        if r.status_code >= 400:
            print("!! create", c["slug"], r.status_code, r.text[:160]); continue
        cid = r.json()["data"]["id"]
        api("POST", "/api/v1/flags", token, json={"challenge_id": cid, "content": c["flag"], "type": "static",
                                                  "data": "case_insensitive" if c.get("any_case") else ""})
        if c.get("also_accept"):
            # other spellings of the same answer, as a regular expression
            api("POST", "/api/v1/flags", token, json={"challenge_id": cid, "content": c["also_accept"],
                                                      "type": "regex", "data": "case_insensitive"})
        for content, cost in c.get("hints", []):
            api("POST", "/api/v1/hints", token, json={"challenge_id": cid, "content": content, "cost": cost, "type": "standard"})
        if c.get("skill"):
            api("POST", "/api/v1/tags", token, json={"challenge_id": cid, "value": "skill: " + c["skill"]})
        if c.get("tier"):
            api("POST", "/api/v1/tags", token, json={"challenge_id": cid, "value": "tier: " + c["tier"]})
        for name in c.get("files", []):
            path = os.path.join(FILES, c["slug"], name)
            with open(path, "rb") as fh:
                api("POST", "/api/v1/files", token,
                    data={"challenge_id": cid, "type": "challenge", "nonce": token},
                    files={"file": (name, fh)})
        by_cat.setdefault(c["category"], 0); by_cat[c["category"]] += 1
    print("created per category:", by_cat, "| texts updated:", updated)


def rules():
    """The Rules page, linked in the menu; made or updated."""
    token = csrf()
    body = {"title": "Rules", "route": "rules", "content": RULES, "format": "markdown",
            "draft": False, "hidden": False, "auth_required": False}
    pages = {p["route"]: p["id"] for p in api("GET", "/api/v1/pages", token).json()["data"]}
    if "rules" in pages:
        r = api("PATCH", f"/api/v1/pages/{pages['rules']}", token, json=body)
    else:
        r = api("POST", "/api/v1/pages", token, json=body)
    print("rules page ->", r.status_code)


def theme():
    # the theme, and the name and tagline again so a rerun picks up changes in .env
    token = csrf()
    r = api("PATCH", "/api/v1/configs", token, json={"ctf_theme": THEME, "theme_color": "#ffcd31", "theme_header": "",
                                                     "ctf_name": EVENT, "ctf_description": TAGLINE})
    print("theme ->", THEME, r.status_code)


if __name__ == "__main__":
    setup()
    print(f"creating {len(CHALLENGES)} challenges...")
    create()
    if RULES:
        rules()
    theme()
    print("done.")
