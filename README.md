# Rice Cup Predictor

Unofficial predictions for the 2026 CanCentral Rice Cup Championships (Crazy 8 Billiards, Winnipeg): every match with the favourite by Fargo and CSR, fair races, a table-by-table schedule estimate and simulated title odds. Not run by the Rice Cup Championships.

## How it stays current

`.github/workflows/refresh.yml` runs every 10 minutes during the event (Nov 20–22). It reads the Main Event and Hard Luck brackets through the official Challonge API (`scripts/challonge_api.py`, using the `CHALLONGE_API_KEY` repository secret), converts them to the format the page reads, and republishes the site only when they changed. Run it any time from **Actions → Refresh brackets and publish → Run workflow**.

## Data

- `raw/b_<slug>.json` – Challonge bracket data for the eight 2026 brackets.
- `raw/players.csv` – CSR for the tournament players only, from the league player-stats sheet.
- `raw/fargo.json` – Fargo ratings from FargoRate's public player search (checked Nov 18, 2026).
- Name matches between the bracket and the sheets are listed in `index.html` (`ALIAS`).

## Model

All ratings are on the Fargo scale; CSR converts through the Midwest Poolplayers Association division table. Game odds use FargoRate's rule (every 100 points doubles the odds); a match is a race to N. Details are in the page footer.
