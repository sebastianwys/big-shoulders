# run every collector, keep going past failures, then rebuild the map data.
# from the repo root:  python -m bot.run_bot

import sys

from bot import build_map_data
from bot.collectors import bls, fred, gazetteer, zillow

COLLECTORS = [
    ("gazetteer", gazetteer.collect),
    ("zillow", zillow.collect),
    ("fred", fred.collect),
    ("bls", bls.collect),
]


def main():
    failures = []
    for name, collect in COLLECTORS:
        try:
            collect()
        except Exception as e:
            print(f"[{name}] FAILED {type(e).__name__}: {e}")
            failures.append(name)

    build_map_data.build()

    if failures:
        print(f"collectors failed: {failures}")
        sys.exit(1)
    print("bot run complete")


if __name__ == "__main__":
    main()
