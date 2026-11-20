#!/usr/bin/env python3
"""Fetch Rice Cup brackets from the official Challonge API (v1) and write them in the
format the dashboard reads (the same shape as challonge.com/<slug>.json).

Usage:  CHALLONGE_API_KEY=... python3 scripts/challonge_api.py ctegjndn jjwwzfei
Writes raw/b_<slug>.json for each slug. Prints a short summary; never prints the key.
Exit code 0 = all written, 1 = an API or conversion problem (existing files are left alone).
"""
import base64, json, os, sys, urllib.error, urllib.request

API = "https://api.challonge.com/v1/tournaments/{slug}.json?include_participants=1&include_matches=1"
FINALS_PAIRS = [(1, 16), (8, 9), (4, 13), (5, 12), (2, 15), (7, 10), (3, 14), (6, 11)]
ORD = {1: "st", 2: "nd", 3: "rd"}


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else ORD.get(n % 10, 'th')}"


def fetch(slug, key):
    req = urllib.request.Request(API.format(slug=slug), headers={
        "Accept": "application/json",
        "User-Agent": "rice-cup-dashboard (GitHub Actions)",
        # v1 accepts the API key as the HTTP Basic password with any user name
        "Authorization": "Basic " + base64.b64encode(f"api:{key}".encode()).decode(),
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def unwrap(item, name):
    return item.get(name, item) if isinstance(item, dict) else item


def scores(csv):
    if not csv:
        return []
    first = str(csv).split(",")[0]
    parts = first.rsplit("-", 1) if first.count("-") >= 1 else []
    try:
        return [int(parts[0]), int(parts[1])] if len(parts) == 2 else []
    except ValueError:
        return []


def finals_titles(max_round):
    names = {max_round: "Finals", max_round - 1: "Semifinals", max_round - 2: "Quarterfinals"}
    return [{"number": r, "title": names.get(r, f"Round {r}")} for r in range(1, max_round + 1)]


def build_stage(matches, names, ttype, state, adv, group_label=None, finals=False):
    # Number matches 1..n in Challonge play order so prerequisites can point at them.
    ms = sorted(matches, key=lambda m: (m.get("suggested_play_order") or 10**9, m["id"]))
    ident = {m["id"]: i + 1 for i, m in enumerate(ms)}
    placeholder = {}
    if finals:
        first = sorted([m for m in ms if m.get("round") == 1 and not m.get("player1_prereq_match_id")
                        and not m.get("player2_prereq_match_id")],
                       key=lambda m: (len(str(m.get("identifier", ""))), str(m.get("identifier", ""))))
        if len(first) == len(FINALS_PAIRS):
            for m, (a, b) in zip(first, FINALS_PAIRS):
                placeholder[m["id"]] = (f"{ordinal(a)} in Group A", f"{ordinal(b)} in Group A")
    by_round = {}
    for m in ms:
        def player(pid):
            return {"id": pid, "display_name": names.get(pid, "")} if pid and names.get(pid) else None
        ph = placeholder.get(m["id"], (None, None))
        out = {
            "identifier": ident[m["id"]],
            "raw_identifier": m.get("identifier"),
            "round": m.get("round"),
            "state": m.get("state"),
            "underway_at": m.get("underway_at"),
            "player1": player(m.get("player1_id")),
            "player2": player(m.get("player2_id")),
            "player1_prereq_identifier": ident.get(m.get("player1_prereq_match_id")),
            "player2_prereq_identifier": ident.get(m.get("player2_prereq_match_id")),
            "player1_is_prereq_match_loser": bool(m.get("player1_is_prereq_match_loser")),
            "player2_is_prereq_match_loser": bool(m.get("player2_is_prereq_match_loser")),
            "player1_placeholder_text": ph[0],
            "player2_placeholder_text": ph[1],
            "winner_id": m.get("winner_id"),
            "scores": scores(m.get("scores_csv")),
        }
        by_round.setdefault(str(m.get("round")), []).append(out)
    rounds = finals_titles(max((m.get("round") or 0) for m in ms)) if finals and ms else []
    stage = {"tournament": {"tournament_type": ttype, "state": state, "participant_count_to_advance": adv},
             "rounds": rounds, "matches_by_round": by_round}
    if group_label:
        stage["name"] = group_label
    return stage


def convert(data):
    t = unwrap(data, "tournament")
    parts = [unwrap(p, "participant") for p in t.get("participants", [])]
    matches = [unwrap(m, "match") for m in t.get("matches", [])]
    names = {}
    for p in parts:
        nm = p.get("display_name") or p.get("name") or ""
        names[p["id"]] = nm
        for gid in p.get("group_player_ids") or []:
            names[gid] = nm
    group_ms = [m for m in matches if m.get("group_id")]
    final_ms = [m for m in matches if not m.get("group_id")]
    ttype = t.get("tournament_type", "double elimination")
    out = build_stage(final_ms, names, ttype, t.get("state"), 1, finals=bool(group_ms))
    out["groups"] = []
    if group_ms:
        out["groups"].append(build_stage(group_ms, names, "double elimination", t.get("state"),
                                         16, group_label="Group A"))
    return out, len(parts), len(matches)


def main():
    key = os.environ.get("CHALLONGE_API_KEY", "").strip()
    if not key:
        print("CHALLONGE_API_KEY is not set; nothing fetched.")
        return 2
    ok = True
    for slug in sys.argv[1:]:
        try:
            converted, np, nm = convert(fetch(slug, key))
        except urllib.error.HTTPError as e:
            print(f"{slug}: Challonge API returned HTTP {e.code}")
            ok = False
            continue
        except Exception as e:  # keep the last good file on any problem
            print(f"{slug}: could not read or convert ({type(e).__name__})")
            ok = False
            continue
        groups = converted["groups"]
        gm = sum(len(v) for g in groups for v in g["matches_by_round"].values())
        fm = sum(len(v) for v in converted["matches_by_round"].values())
        print(f"{slug}: {np} participants, {nm} matches (group {gm}, bracket {fm})")
        with open(f"raw/b_{slug}.json", "w", encoding="utf-8") as f:
            json.dump(converted, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
