#!/usr/bin/env python3
"""Dry run of the refresh (no publish): prints the summary line, including tables found."""
import subprocess, sys
r = subprocess.run([sys.executable, "scripts/challonge_api.py", "ctegjndn"], capture_output=True, text=True)
print(r.stdout, r.stderr)
print(subprocess.run(["bash", "-c", "grep -o '\"station\":{\"id\":[0-9]*,\"name\":\"[^\"]*\"' raw/b_ctegjndn.json | sort | uniq -c | head -15"], capture_output=True, text=True).stdout)
