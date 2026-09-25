"""
market_data.py
------------------------------------------------------------
Fetches macro data from FRED (interest rate, inflation) and
Frankfurter (USD/TRY exchange rate), then produces a single clean
long-format CSV ready for Power BI.

Output: market_data.csv
Columns: date | value | Indicator

Before running:
    pip install requests pandas
Then paste YOUR own key into the FRED_API_KEY line below.
------------------------------------------------------------
"""

import requests
import pandas as pd

# ============ SETTINGS (edit this part) ============
FRED_API_KEY = "4bb9ff94abaef6d8d63dbd12678e7c5e"   # <-- your 32-char key inside the quotes
START_DATE   = "2015-01-01"                 # start date of the data
OUTPUT_FILE  = "market_data.csv"            # name of the file to create

# FRED series: series_id -> readable label
FRED_SERIES = {
    "FEDFUNDS": "Interest Rate",   # US policy rate (monthly)
    "CPIAUCSL": "Inflation",       # US consumer price index (monthly)
}
# ===================================================


def get_fred(series_id, label):
    """Fetch a single FRED series and return a clean DataFrame."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": START_DATE,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    observations = response.json()["observations"]

    df = pd.DataFrame(observations)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    # FRED returns missing values as "." -> becomes NaN when converted, then dropped
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["Indicator"] = label
    print(f"  FRED  {series_id:10s} ({label:13s}): {len(df):4d} rows")
    return df


def get_frankfurter():
    """Fetch USD/TRY and resample it to monthly (to align with FRED)."""
    url = f"https://api.frankfurter.dev/v1/{START_DATE}.."
    params = {"base": "USD", "symbols": "TRY"}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    rates = response.json()["rates"]  # shape: {date: {"TRY": value}}

    df = pd.DataFrame([{"date": d, "value": v["TRY"]} for d, v in rates.items()])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    # Daily -> month-start average, so all three series share the same axis
    df = df.set_index("date").resample("MS")["value"].mean().reset_index()
    df["Indicator"] = "Exchange Rate"
    print(f"  FRANK USD/TRY      (Exchange Rate): {len(df):4d} rows (monthly)")
    return df


def main():
    if FRED_API_KEY.startswith("PASTE_YOUR"):
        raise SystemExit("ERROR: Paste your FRED_API_KEY first.")

    print("Fetching data...")
    frames = [get_fred(series_id, label) for series_id, label in FRED_SERIES.items()]
    frames.append(get_frankfurter())

    full = pd.concat(frames, ignore_index=True)
    full["value"] = full["value"].round(4)
    full = full.sort_values(["Indicator", "date"]).reset_index(drop=True)

    # utf-8-sig -> Power BI / Excel detect the encoding correctly
    full.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\nDone. {len(full)} rows total -> {OUTPUT_FILE}")
    print("\nSummary per indicator:")
    print(full.groupby("Indicator")["value"].agg(["count", "min", "max"]))


if __name__ == "__main__":
    main()