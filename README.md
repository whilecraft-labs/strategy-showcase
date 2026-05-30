# Strategies Dashboard

Public display layer for long-only momentum strategies. All strategy logic
lives in a private engine repo; this repo only contains the Streamlit app
and pre-computed JSON outputs.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Deploy

Push this repo to GitHub (public), then connect at
[share.streamlit.io](https://share.streamlit.io). Free tier, deploys
automatically on push. The app reads only files in `public_data/`, which is
updated by a GitHub Action in the private engine repo.

## Data refresh

`public_data/` is rewritten by a daily cron in the private repo. It contains:

- `strategies.json` — index of all strategies
- `<strategy_id>/meta.json` — descriptive metadata + summary stats
- `<strategy_id>/nav.json` — daily NAV time series (strategy & benchmark)
- `<strategy_id>/holdings.json` — current portfolio
- `<strategy_id>/rebalance_log.json` — recent rebalance history
