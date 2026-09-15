# run every collector, keep going past failures, then rebuild the map data.
# from the repo root:  python -m bot.run_bot

import importlib
import pkgutil
import sys

from bot import build_map_data
from bot import collectors as collectors_pkg


# every module in bot/collectors with a collect() runs. gazetteer goes first
# because bls and the build key on its centroids, the rest alphabetically
def discover():
    names = sorted(module.name for module in pkgutil.iter_modules(collectors_pkg.__path__))
    ordered = ["gazetteer"] + [name for name in names if name != "gazetteer"]
    found = []
    for name in ordered:
        module = importlib.import_module(f"bot.collectors.{name}")
        if callable(getattr(module, "collect", None)):
            found.append((name, module.collect))
    return found


def main():
    failures = []
    for name, collect in discover():
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
