"""rev2: fixes tz error in binance() (rev1 failed there 1 Nov). Gold data for the session IFVG test (SESSION_IFVG_SPEC_rev2.md, Part A).

Runs inside GitHub Actions in Lazzmatazz74/btc-futures-data (the Claude workspace cannot reach these sites).
Step 1 (workflow, not this file): dukascopy-node writes raw bid and ask 1m CSVs per year into raw_gold/.
Step 2 (this file, mode "merge"): bid + ask -> mid 1m per year -> data/gold/XAUUSD_1m_mid_<Y>.csv.gz
Step 3 (this file, mode "binance"): Binance XAUUSDT USD-M perp 1m from data.binance.vision (2026-01 ->)
         -> data/gold/XAUUSDT_perp_1m.csv.gz
Step 4 (this file, mode "check"): sanity report -> data/gold/gold_data_check.json
   per year: rows, first/last time, min/max mid, share of minutes with ask < bid;
   overlap with Binance: median and p99 of |mid - perp close| / perp close in percent.
Times are UTC, open time of the minute, epoch milliseconds.
"""
import glob, gzip, io, json, os, sys, zipfile, urllib.request
import pandas as pd

RAW = 'raw_gold'
OUT = 'data/gold'
os.makedirs(OUT, exist_ok=True)


def read_duka(path):
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    return df[['timestamp', 'open', 'high', 'low', 'close']].set_index('timestamp')


def merge():
    for bid_path in sorted(glob.glob(f'{RAW}/bid_*.csv')):
        y = bid_path.split('_')[-1][:4]
        ask_path = f'{RAW}/ask_{y}.csv'
        if not os.path.exists(ask_path):
            print('missing ask for', y); continue
        b, a = read_duka(bid_path), read_duka(ask_path)
        j = b.join(a, lsuffix='_b', rsuffix='_a', how='inner')
        mid = pd.DataFrame({k: (j[f'{k}_b'] + j[f'{k}_a']) / 2 for k in ['open', 'high', 'low', 'close']})
        mid['spread'] = j['close_a'] - j['close_b']
        mid.index.name = 'open_time'
        mid.round(4).to_csv(f'{OUT}/XAUUSD_1m_mid_{y}.csv.gz', compression='gzip')
        print(y, 'bid', len(b), 'ask', len(a), 'mid', len(mid))


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except Exception as e:
        print('skip', url, e); return None


def binance():
    cols = ['open_time', 'open', 'high', 'low', 'close', 'volume']
    frames = []
    today = pd.Timestamp.now("UTC").normalize().tz_localize(None)
    m = pd.Timestamp('2026-01-01')
    while m < today:
        url = f'https://data.binance.vision/data/futures/um/monthly/klines/XAUUSDT/1m/XAUUSDT-1m-{m:%Y-%m}.zip'
        raw = fetch(url)
        if raw is None:  # month not published yet -> daily files
            d = m
            while d < min(m + pd.offsets.MonthBegin(1), today):
                r2 = fetch(f'https://data.binance.vision/data/futures/um/daily/klines/XAUUSDT/1m/XAUUSDT-1m-{d:%Y-%m-%d}.zip')
                if r2: frames.append(_unzip(r2, cols))
                d += pd.Timedelta(days=1)
        else:
            frames.append(_unzip(raw, cols))
        m += pd.offsets.MonthBegin(1)
    df = pd.concat(frames).drop_duplicates('open_time').sort_values('open_time')
    df.to_csv(f'{OUT}/XAUUSDT_perp_1m.csv.gz', index=False, compression='gzip')
    print('binance rows', len(df))


def _unzip(raw, cols):
    z = zipfile.ZipFile(io.BytesIO(raw))
    df = pd.read_csv(z.open(z.namelist()[0]), header=None)
    if not str(df.iloc[0, 0]).isdigit():  # header row present
        df = df.iloc[1:]
    df = df.iloc[:, :6]; df.columns = cols
    return df.astype({'open_time': 'int64', 'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})


def check():
    rep = {'years': {}}
    mids = []
    for p in sorted(glob.glob(f'{OUT}/XAUUSD_1m_mid_*.csv.gz')):
        df = pd.read_csv(p)
        y = p[-11:-7]
        rep['years'][y] = dict(rows=len(df), first=str(pd.to_datetime(df.open_time.min(), unit='ms')),
                               last=str(pd.to_datetime(df.open_time.max(), unit='ms')),
                               min_mid=float(df.low.min()), max_mid=float(df.high.max()),
                               neg_spread_share=float((df.spread < 0).mean()))
        if int(y) >= 2026: mids.append(df)
    pp = f'{OUT}/XAUUSDT_perp_1m.csv.gz'
    if mids and os.path.exists(pp):
        perp = pd.read_csv(pp)
        j = pd.concat(mids).merge(perp[['open_time', 'close']], on='open_time', suffixes=('_mid', '_perp'))
        dev = ((j.close_mid - j.close_perp).abs() / j.close_perp * 100)
        rep['overlap'] = dict(minutes=len(j), median_abs_dev_pct=float(dev.median()), p99_abs_dev_pct=float(dev.quantile(.99)))
    json.dump(rep, open(f'{OUT}/gold_data_check.json', 'w'), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    {'merge': merge, 'binance': binance, 'check': check}[sys.argv[1]]()
