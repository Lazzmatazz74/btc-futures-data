# Data-pipeline fix — install steps (rev1, 2026-09-24)

Repo: `Lazzmatazz74/btc-futures-data`. Nothing existing is overwritten or deleted; the old workflows are only **disabled**.

## What's in `repo_upload_rev2.zip`

| File | Goes to | Replaces (old stays in repo) |
|---|---|---|
| `binance_data_downloader_rev6.py` | repo root | `binance_data_downloader_rev5.py` |
| `prep_candles_rev2.py` | repo root | `prep_candles_rev1.py` (session copy) |
| `forward_signal_log_rev2.py` | repo root | `forward_signal_log_rev1.py` |
| `.github/workflows/fetch_data_rev4.yml` | `.github/workflows/` | `fetch_data.yml` ("Fetch fresh futures data (daily top-up)") |
| `.github/workflows/fetch_extra_data_rev3.yml` | `.github/workflows/` | `fetch_extra_data_rev2.yml` ("Fetch extra data + forward log") |

## Steps

1. Upload the zip contents to the repo root, keeping the `.github/workflows/` folder: **Add file → Upload files**, drag all five in, then commit. If the web uploader drops the `.github` folder, create the two workflow files with **Add file → Create new file** instead, using the paths `.github/workflows/fetch_data_rev4.yml` and `.github/workflows/fetch_extra_data_rev3.yml`, and paste the contents in.
2. **Disable the two old workflows.** Go to Actions, click the workflow, open the **…** menu and choose **Disable workflow**:
   - "Fetch fresh futures data (daily top-up)". This matters most: if it stays on, the old downloader still runs at 02:00 and can still create gaps.
   - "Fetch extra data + forward log"
3. Actions → **"Fetch futures data rev4 (gap-safe, 2 runs/day)"** → **Run workflow**. This should add 23 Sep. A green tick means no new gaps and the lag is under 60h. A red X means open `data/status_download.json` and read `problems`.
4. Actions → **"Fetch extra data + forward log rev3"** → **Run workflow**. This creates `data/forward/forward_signals_rev2.csv` and `forward_runs_rev2.csv`.

## After install

- **Schedule:** candles run at 02:00 and 08:00 UTC; extra data and the forward log run at 02:30 and 08:30 UTC (04:00/10:00 and 04:30/10:30 Bratislava summer time).
- **Health file:** `data/status_download.json` shows every file's last bar, its lag, the day it is waiting for and any gaps.
- **Live signals:** in the forward log, `live=True` means the signal appeared the first time its entry bar was in the data. The G3 verdict (after 30 or more live X3 shorts) uses only those rows.
- **First rev2 run:** it has no earlier run to compare with, so XRP/BNB signals up to that run's data end are marked backfill (`live=False`). BTC/ETH start from rev1's last data end (23 Sep 00:00 UTC), so their signals after that can count as live.

## Not verified

- **Archive timing:** that Binance's daily archive for yesterday is out by 08:00 UTC. The workspace can't reach Binance to check when files are published.
- **Workflow test:** that the workflows run on GitHub. The scripts were tested offline on a copy of the repo data; the workflow files themselves could not be run from here.
