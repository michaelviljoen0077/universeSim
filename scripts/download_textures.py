"""Download photoreal planet/star textures into ``assets/textures/``.

Textures are the 2K maps from Solar System Scope, distributed under Creative Commons
Attribution 4.0 (CC BY 4.0) — free to use, including commercially, with attribution.
See ``assets/CREDITS.md`` (written by this script).

Usage:
    python scripts/download_textures.py            # 2k maps (default)
    python scripts/download_textures.py --res 8k   # higher-res where available

Re-running skips files that already exist. Missing textures are non-fatal: the app
falls back to flat-shaded colours for any body whose map isn't present.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

# Texture key -> remote filename stem (without resolution prefix / extension).
TEXTURES = {
    "sun": "sun",
    "mercury": "mercury",
    "venus": "venus_surface",
    "earth": "earth_daymap",
    "earth_clouds": "earth_clouds",
    "mars": "mars",
    "jupiter": "jupiter",
    "saturn": "saturn",
    "uranus": "uranus",
    "neptune": "neptune",
    "moon": "moon",
    "stars_milky_way": "stars_milky_way",
}

# The site has used a couple of path layouts over time; try each until one works.
URL_BASES = [
    "https://www.solarsystemscope.com/textures/download/",
    "https://solarsystemscope.com/textures/download/",
    "https://www.solarsystemscope.com/download/",
]

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "textures"

_CREDITS = """\
# Texture Credits

Planet, moon, and star textures by **Solar System Scope**
(https://www.solarsystemscope.com/textures/), distributed under the
Creative Commons Attribution 4.0 International license (CC BY 4.0).

You may use, adapt, and share these textures for any purpose, including
commercially, provided attribution is given.
"""


def _download(stem: str, res: str, dest: Path) -> bool:
    filename = f"{res}_{stem}.jpg"
    last_err = None
    for base in URL_BASES:
        url = base + filename
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "universesim/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if len(data) < 1024:  # too small to be a real image
                last_err = f"suspiciously small response ({len(data)} bytes)"
                continue
            dest.write_bytes(data)
            print(f"  ok   {dest.name}  ({len(data) // 1024} KB)  <- {url}")
            return True
        except Exception as exc:  # noqa: BLE001 - report and try next base
            last_err = f"{type(exc).__name__}: {exc}"
    print(f"  FAIL {filename}  ({last_err})")
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download Solar System Scope textures.")
    parser.add_argument("--res", default="2k", choices=["2k", "8k"],
                        help="Texture resolution (default: 2k).")
    parser.add_argument("--force", action="store_true", help="Re-download existing files.")
    args = parser.parse_args(argv)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR.parent / "CREDITS.md").write_text(_CREDITS, encoding="utf-8")

    print(f"Downloading {args.res} textures into {ASSETS_DIR}")
    ok = 0
    for key, stem in TEXTURES.items():
        dest = ASSETS_DIR / f"{key}.jpg"
        if dest.exists() and not args.force:
            print(f"  skip {dest.name} (exists)")
            ok += 1
            continue
        if _download(stem, args.res, dest):
            ok += 1

    print(f"\nDone: {ok}/{len(TEXTURES)} textures available in {ASSETS_DIR}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
