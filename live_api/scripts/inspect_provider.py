"""
Run this from the repo root, with your venv active, on a machine that can
reach psx.com.pk:

    python live_api/scripts/inspect_provider.py OGDC

It prints the exact column names and values psxdata.quote() returns for one
symbol, so we can fix providers.py's _pick() field-name guesses to match
reality instead of the assumed names from the original plan.
"""
import sys

import psxdata


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "OGDC"
    df = psxdata.quote(symbol)
    print(f"type: {type(df)}")
    print(f"shape: {getattr(df, 'shape', None)}")
    print(f"columns: {list(df.columns)}")
    print("---- first row as dict ----")
    if not df.empty:
        row = df.iloc[0].to_dict()
        for k, v in row.items():
            print(f"  {k!r}: {v!r}  (type={type(v).__name__})")
    else:
        print("  <empty dataframe>")


if __name__ == "__main__":
    main()
