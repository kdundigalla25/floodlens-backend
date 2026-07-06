"""Inner-join two CSV files on a key column, normalizing the keys first.

One file (~5M rows) is streamed in chunks so memory stays flat; the smaller
file is held in memory as the lookup table. Keys are normalized before joining:
all whitespace removed (including spaces in the middle) and lowercased.
"""

import argparse
import os

import pandas as pd


def normalize_key(series: pd.Series) -> pd.Series:
    """Lowercase and strip ALL whitespace (edges + internal) from a key column."""
    return (
        series.astype("string")            # nullable string; keeps NaN as <NA>
        .str.replace(r"\s+", "", regex=True)
        .str.lower()
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--big", default="file_with_parno.csv",
                        help="Path to the large CSV (streamed in chunks).")
    parser.add_argument("--big-key", default="parno",
                        help="Join column name in the big file.")
    parser.add_argument("--small", default="file_with_pid.csv",
                        help="Path to the smaller CSV (loaded fully into memory).")
    parser.add_argument("--small-key", default="PID",
                        help="Join column name in the small file.")
    parser.add_argument("--output", default="joined.csv",
                        help="Output CSV path.")
    parser.add_argument("--chunksize", type=int, default=500_000,
                        help="Rows per chunk when streaming the big file.")
    args = parser.parse_args()

    # Fresh output each run (we append per-chunk below).
    if os.path.exists(args.output):
        os.remove(args.output)

    # --- Load the small file fully and normalize its key ---
    small = pd.read_csv(args.small, dtype=str)
    small["_join_key"] = normalize_key(small[args.small_key])
    # Drop rows whose key is empty/NA so blanks don't mass-match each other.
    before = len(small)
    small = small.dropna(subset=["_join_key"])
    small = small[small["_join_key"] != ""]
    print(f"Loaded small file '{args.small}': {before} rows "
          f"({len(small)} with a usable key).")

    # --- Stream the big file in chunks, join, and append matches ---
    total_in = 0
    total_matched = 0
    first_write = True

    for chunk in pd.read_csv(args.big, dtype=str, chunksize=args.chunksize):
        total_in += len(chunk)
        chunk["_join_key"] = normalize_key(chunk[args.big_key])

        joined = chunk.merge(
            small,
            on="_join_key",
            how="inner",
            suffixes=("_big", "_small"),
        )
        joined = joined.drop(columns=["_join_key"])

        if not joined.empty:
            joined.to_csv(args.output, mode="a", index=False, header=first_write)
            first_write = False
            total_matched += len(joined)

        print(f"  processed {total_in:,} big rows... {total_matched:,} matches so far")

    print(f"\nDone. Read {total_in:,} rows from '{args.big}', "
          f"wrote {total_matched:,} matched rows to '{args.output}'.")


if __name__ == "__main__":
    main()
