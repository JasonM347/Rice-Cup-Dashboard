#!/usr/bin/env python3
"""One-off check of the Challonge v2.1 API with the organizer's Client ID and Secret.
Prints HTTP statuses and the shape of the data (field names, one sample record).
Never prints the client id, secret or token."""
import json, os, sys, urllib.error, urllib.parse, urllib.request

CID = os.environ.get("CHALLONGE_CLIENT_ID", "").strip()
SEC = os.environ.get("CHALLONGE_CLIENT_SECRET", "").strip()
BASE = "https://api.challonge.com/v2.1"
SLUG = "ctegjndn"


def clean(text):
    for s in (CID, SEC):
        if s:
            text = text.replace(s, "***")
    return text[:600]


def call(url, data=None, headers=None):
    h = {"User-Agent": "rice-cup-dashboard/1.0 (+https://jasonm347.github.io/Rice-Cup-Dashboard/)"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, type(e).__name__


def token():
    for scope in ("me tournaments:read matches:read participants:read",
                  "application:manage tournaments:read matches:read participants:read",
                  "application:organizer", None):
        form = {"grant_type": "client_credentials", "client_id": CID, "client_secret": SEC}
        if scope:
            form["scope"] = scope
        st, body = call("https://api.challonge.com/oauth/token",
                        urllib.parse.urlencode(form).encode(),
                        {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
        print(f"token scope={scope!r}: HTTP {st}")
        if st == 200:
            j = json.loads(body)
            print("  granted scope:", j.get("scope"), "| expires_in:", j.get("expires_in"))
            return j["access_token"]
        print("  ", clean(body))
    return None


def shape(name, st, body):
    print(f"\n== {name}: HTTP {st}")
    try:
        j = json.loads(body)
    except Exception:
        print("  ", clean(body)); return
    print("  top keys:", list(j) if isinstance(j, dict) else type(j).__name__)
    d = j.get("data") if isinstance(j, dict) else None
    items = d if isinstance(d, list) else [d] if d else []
    print("  items:", len(items), "| meta:", j.get("meta"), "| links:", j.get("links"))
    if items:
        it = items[0]
        print("  type:", it.get("type"))
        print("  attribute keys:", sorted((it.get("attributes") or {}).keys()))
        print("  relationship keys:", sorted((it.get("relationships") or {}).keys()))
        print("  sample:", json.dumps(it)[:2500])
    if isinstance(j, dict) and j.get("included"):
        print("  included types:", sorted({x.get("type") for x in j["included"]}))
    if not items:
        print("  ", clean(body))


def main():
    if not (CID and SEC):
        print("CHALLONGE_CLIENT_ID / CHALLONGE_CLIENT_SECRET not set"); return 2
    tok = token()
    if not tok:
        return 1
    h = {"Authorization-Type": "v2", "Authorization": f"Bearer {tok}",
         "Content-Type": "application/vnd.api+json", "Accept": "application/json"}
    for name, path in [("tournament", f"/tournaments/{SLUG}.json"),
                       ("matches p1", f"/tournaments/{SLUG}/matches.json?page=1&per_page=25"),
                       ("participants p1", f"/tournaments/{SLUG}/participants.json?page=1&per_page=25"),
                       ("my tournaments", "/tournaments.json?page=1&per_page=5"),
                       ("application tournaments", "/application/tournaments.json?page=1&per_page=5")]:
        st, body = call(BASE + path, headers=h)
        shape(name, st, body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
