"""Download the case-study specs at the pinned commits and verify their SHA-256.

    python specs/fetch.py            # writes specs/data/<file>
Stdlib only. Exits non-zero if a hash differs (the upstream file changed or the download is corrupt).
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent


def main() -> int:
    manifest = json.loads((HERE / "manifest.json").read_text())
    out = HERE / "data"
    out.mkdir(exist_ok=True)
    bad = 0
    for s in manifest["specs"]:
        url = f"https://raw.githubusercontent.com/{s['repo']}/{s['commit']}/{s['path']}"
        data = urllib.request.urlopen(url, timeout=120).read()
        digest = hashlib.sha256(data).hexdigest()
        ok = digest == s["sha256"]
        bad += not ok
        (out / s["file"]).write_bytes(data)
        print(f"{'OK  ' if ok else 'DIFF'} {s['name']:11} {len(data):>10,} bytes  {digest[:12]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
