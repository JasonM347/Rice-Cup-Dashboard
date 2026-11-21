#!/usr/bin/env python3
"""One-off: where does the v2.1 API put table (station) assignments? Prints shapes only."""
import json, sys
sys.path.insert(0, "scripts")
import challonge_api as c
tok = c.get_token()
h = {"Authorization-Type": "v2", "Authorization": f"Bearer {tok}", "Content-Type": "application/vnd.api+json"}
j = c.call(f"{c.BASE}/tournaments/ctegjndn.json", headers=h)
inc = j.get("included") or []
ms = [x for x in inc if x.get("type") == "match"]
op = [x for x in ms if (x.get("attributes") or {}).get("state") == "open"]
print("tournament endpoint: matches", len(ms), "open", len(op), "stations included", sum(1 for x in inc if x.get("type") == "station"))
if op:
    print("open match relationships:", json.dumps(op[0].get("relationships"))[:600])
s = c.call(f"{c.BASE}/tournaments/ctegjndn/stations.json", headers=h)
d = s.get("data") or []
print("stations endpoint:", len(d))
for x in d[:3]:
    print("  ", json.dumps(x)[:700])
m = c.call(f"{c.BASE}/tournaments/ctegjndn/matches.json?state=open&page=1&per_page=25", headers=h)
md = m.get("data") or []
print("matches endpoint (open):", len(md), (m.get("meta") or {}))
if md:
    print("  station rel:", json.dumps((md[0].get("relationships") or {}).get("station"))[:300])
