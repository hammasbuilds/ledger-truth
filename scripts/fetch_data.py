"""Pull FinQA from the authors' repository.

    python scripts/fetch_data.py

103 MB across three files. Fetched from `raw.githubusercontent.com` in byte
ranges: codeload is throttled to near-nothing on this link, raw is not, and a
single GET of a 78 MB file still truncates often enough to be worth guarding
against. Each file is checked against its Content-Length and deleted if short,
because a half-written JSON fails much later and much less clearly.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
BASE = "https://raw.githubusercontent.com/czyssrs/FinQA/main/dataset"
SPLITS = ("train", "dev", "test")
CHUNK = 4_000_000

# The published split sizes. A different count is a different benchmark.
EXPECT = {"train": 6_251, "dev": 883, "test": 1_147}


def expected_size(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ledger-truth"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return int(response.headers["Content-Length"])


def fetch(split: str) -> Path:
    out = DATA / f"{split}.json"
    url = f"{BASE}/{split}.json"
    total = expected_size(url)

    if out.exists() and out.stat().st_size == total:
        print(f"  {out.name} already complete ({total / 1e6:.0f} MB)")
        return out

    print(f"  {out.name}  {total / 1e6:.0f} MB ", end="", flush=True)
    written = 0
    with out.open("wb") as handle:
        while written < total:
            end = min(written + CHUNK, total) - 1
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "ledger-truth", "Range": f"bytes={written}-{end}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    block = response.read()
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"\n    failed at byte {written:,}: {exc}")
                raise
            if not block:
                raise OSError(f"{out.name}: empty response at byte {written:,}")
            handle.write(block)
            written += len(block)
            print(".", end="", flush=True)

    got = out.stat().st_size
    if got != total:
        out.unlink()
        raise OSError(f"{out.name}: got {got:,} bytes, expected {total:,}. Removed.")
    print(" ok")
    return out


def main() -> None:
    DATA.mkdir(exist_ok=True)
    print("fetching FinQA")
    for split in SPLITS:
        fetch(split)

    print("\nchecking")
    ok = True
    for split in SPLITS:
        rows = json.loads((DATA / f"{split}.json").read_text(encoding="utf-8"))
        good = len(rows) == EXPECT[split]
        ok &= good
        print(f"  {split:<6}{len(rows):>6,}  {'ok' if good else f'EXPECTED {EXPECT[split]:,}'}")

    if not ok:
        print("\nThe splits are not the published ones; stop rather than measure "
              "something else.", file=sys.stderr)
        raise SystemExit(1)
    print("\nFinQA ready")


if __name__ == "__main__":
    main()
