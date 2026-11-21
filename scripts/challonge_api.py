#!/usr/bin/env python3
"""Refresh Rice Cup brackets from the official Challonge API (v2.1) with the organizer's
Client ID and Secret, and update raw/b_<slug>.json in place.

The v2.1 API gives each match's players, state, scores and winner but not the bracket
wiring (which match feeds which). That wiring is fixed once a bracket is drawn and is
already in raw/b_<slug>.json (saved from challonge.com/<slug>.json), so this script only
updates the live fields of matches it already knows, matched by Challonge match id.

Usage:  CHALLONGE_CLIENT_ID=... CHALLONGE_CLIENT_SECRET=... python3 scripts/challonge_api.py ctegjndn jjwwzfei
Exit codes: 0 = done, 1 = API or conversion problem (files left alone), 2 = no credentials.
Never prints the client id, secret or token.
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request

CID = os.environ.get("CHALLONGE_CLIENT_ID", "").strip()
SEC = os.environ.get("CHALLONGE_CLIENT_SECRET", "").strip()
BASE = "https://api.challonge.com/v2.1"
UA = "rice-cup-dashboard/1.0 (+https://jasonm347.github.io/Rice-Cup-Dashboard/)"


def call(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=40) as r:
        return json.load(r)


# Optional: reuse one login token across runs (it lasts 7 days) to save API requests.
# The file lives only on the runner (outside the repo) and is never printed.
TOKEN_FILE = os.environ.get("CHALLONGE_TOKEN_FILE", "").strip()


def get_token():
    if TOKEN_FILE and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            tok = f.read().strip()
        if tok:
            return tok
    form = {"grant_type": "client_credentials", "client_id": CID, "client_secret": SEC,
            "scope": "me tournaments:read matches:read participants:read"}
    j = call("https://api.challonge.com/oauth/token", urllib.parse.urlencode(form).encode(),
             {"Content-Type": "application/x-www-form-urlencoded"})
    if TOKEN_FILE:
        with open(TOKEN_FILE, "w") as f:
            f.write(j["access_token"])
    return j["access_token"]


def forget_token():
    if TOKEN_FILE and os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def fetch(slug, token):
    """Return (tournament attributes, matches, participant names). Usually one request:
    the tournament endpoint includes its matches and participants; pages only if not."""
    h = {"Authorization-Type": "v2", "Authorization": f"Bearer {token}",
         "Content-Type": "application/vnd.api+json"}
    j = call(f"{BASE}/tournaments/{slug}.json", headers=h)
    t = j["data"]
    inc = j.get("included") or []
    matches = [x for x in inc if x.get("type") == "match"]
    parts = [x for x in inc if x.get("type") == "participant"]
    rel = t.get("relationships") or {}
    want_m = len((rel.get("matches") or {}).get("data") or []) or \
        ((rel.get("matches") or {}).get("links") or {}).get("meta", {}).get("count", 0)
    want_p = t["attributes"].get("participants_count") or 0

    def pages(kind):
        out, url = [], f"{BASE}/tournaments/{slug}/{kind}.json?page=1&per_page=100"
        while url:
            p = call(url, headers=h)
            out += p.get("data") or []
            url = (p.get("links") or {}).get("next")
        return out

    if len(matches) < want_m:
        matches = pages("matches")
    if len(parts) < want_p:
        parts = pages("participants")
    names = {str(p["id"]): (p.get("attributes") or {}).get("name") or "" for p in parts}
    stations = {str(x["id"]): (x.get("attributes") or {}).get("name") or ""
                for x in inc if x.get("type") == "station"}
    # The tournament endpoint links tables to matches from the table's side, not the match's,
    # so build match id -> (station id, name) from whatever match reference each table carries.
    on_table = {}
    for x in inc:
        if x.get("type") != "station":
            continue
        a, rel = x.get("attributes") or {}, x.get("relationships") or {}
        mids = [a.get(k) for k in ("match_id", "current_match_id") if a.get(k)]
        for r in rel.values():
            d = (r or {}).get("data") if isinstance(r, dict) else None
            for dd in (d if isinstance(d, list) else [d]):
                if isinstance(dd, dict) and dd.get("type") == "match" and dd.get("id"):
                    mids.append(dd["id"])
        for mid in mids:
            on_table[str(mid)] = (str(x["id"]), a.get("name") or "")
    stations["__by_match__"] = on_table
    return t["attributes"], matches, names, stations


def score_pair(attr, p1, p2):
    pbp = {str(x.get("participant_id")): x.get("scores") or [] for x in attr.get("points_by_participant") or []}
    a, b = pbp.get(str(p1)), pbp.get(str(p2))
    if a and b:
        return [int(sum(a)), int(sum(b))]
    s = str(attr.get("scores") or "").split(",")[0].replace(" ", "")
    if attr.get("state") == "complete" and s.count("-") == 1:
        try:
            x, y = s.split("-")
            return [int(x), int(y)]
        except ValueError:
            pass
    return []


def update(slug, token):
    path = f"raw/b_{slug}.json"
    with open(path, encoding="utf-8") as f:
        base = json.load(f)
    tattr, matches, names, stations = fetch(slug, token)
    known = {}
    for stage in [base] + (base.get("groups") or []):
        for lst in (stage.get("matches_by_round") or {}).values():
            for m in lst or []:
                if m.get("id") is not None:
                    known[str(m["id"])] = m
                st = m.get("station") or {}
                if st.get("id") and st.get("name"):
                    stations.setdefault(str(st["id"]), st["name"])
    if matches and not known:
        print(f"{slug}: bracket is drawn on Challonge ({len(matches)} matches) but its layout isn't saved yet; "
              "save challonge.com/{slug}.json once to raw/. Left unchanged.".replace("{slug}", slug))
        return True
    by_match = stations.pop("__by_match__", {})
    hit = done = tabled = 0
    for x in matches:
        m = known.get(str(x["id"]))
        if m is None:
            continue
        hit += 1
        a, rel = x.get("attributes") or {}, x.get("relationships") or {}
        ids = []
        for side in ("player1", "player2"):
            d = (rel.get(side) or {}).get("data")
            pid = d.get("id") if d else None
            ids.append(pid)
            m[side] = {"id": int(pid), "display_name": names.get(str(pid), "")} if pid and names.get(str(pid)) else None
        m["state"] = a.get("state", m.get("state"))
        m["winner_id"] = int(a["winner_id"]) if a.get("winner_id") else None
        m["scores"] = score_pair(a, ids[0], ids[1])
        ts = a.get("timestamps") or {}
        m["underway_at"] = ts.get("underway_at")
        # Table the organizer assigned (Challonge "station"); kept as {id, name} like challonge.com's JSON
        sd = (rel.get("station") or {}).get("data")
        sid = str(sd["id"]) if sd and sd.get("id") else None
        if sid:
            m["station"] = {"id": int(sid), "name": stations.get(sid, "")}
        elif str(x["id"]) in by_match:
            bsid, bname = by_match[str(x["id"])]
            m["station"] = {"id": int(bsid), "name": bname or stations.get(bsid, "")}
        elif not by_match and m["state"] == "open":
            pass   # API sent no table links at all: keep the table from the last challonge.com copy
        else:
            m["station"] = None
        tabled += m.get("station") is not None
        # Challonge has no completed time in v2.1; the last update of a finished match is close enough
        m["completed_at"] = ts.get("updated_at") if m["state"] == "complete" else None
        done += m["state"] == "complete"
    if known and hit < len(known):
        print(f"{slug}: only {hit} of {len(known)} saved matches came back from the API; left unchanged.")
        return False
    base.setdefault("tournament", {})["state"] = tattr.get("state")
    for g in base.get("groups") or []:
        g.setdefault("tournament", {})["state"] = tattr.get("state")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{slug}: {tattr.get('state')}, {len(names)} players, {hit} matches updated ({done} complete, "
          f"{tabled} on a table; {len(stations)} tables, {len(by_match)} table links)")
    if len(matches) > hit:
        print(f"::warning::{slug}: {len(matches) - hit} new matches on Challonge (e.g. the top-16 bracket) "
              f"aren't in raw/b_{slug}.json yet; save challonge.com/{slug}.json there to show them.")
    return True


def main():
    if not (CID and SEC):
        print("CHALLONGE_CLIENT_ID / CHALLONGE_CLIENT_SECRET are not set; nothing fetched.")
        return 2
    try:
        token = get_token()
    except urllib.error.HTTPError as e:
        print(f"Challonge login failed: HTTP {e.code}")
        return 1
    ok = True
    for slug in sys.argv[1:]:
        try:
            ok = update(slug, token) and ok
        except urllib.error.HTTPError as e:
            print(f"{slug}: Challonge API returned HTTP {e.code}")
            if e.code == 401:
                forget_token()   # expired or revoked: log in again next time
            ok = False
        except Exception as e:  # keep the last good file on any problem
            print(f"{slug}: could not read or convert ({type(e).__name__}: {e})")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
