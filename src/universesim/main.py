"""Entry point: ``python -m universesim`` or the ``universesim`` console script."""

from __future__ import annotations

import argparse

from universesim import scenarios

SCENARIOS = scenarios.SLUGS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="universesim", description="3D space sandbox.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="solar-system",
                        help="Which preset system to load.")
    parser.add_argument("--headless", action="store_true",
                        help="Build and step the sim without opening a window (smoke test).")
    parser.add_argument("--frames", type=int, default=120,
                        help="Headless only: number of frames to step before exiting.")
    args = parser.parse_args(argv)

    factory = SCENARIOS[args.scenario]
    world = factory()

    # Import the renderer lazily so headless physics work doesn't require a GPU import
    # to *parse*, and so an import error surfaces with a clear message.
    from universesim.render.app import UniverseApp

    app = UniverseApp(world=world, headless=args.headless, scenario_factory=factory)

    if args.headless:
        for _ in range(args.frames):
            app.taskMgr.step()
        print(f"[headless] stepped {args.frames} frames; "
              f"sim time = {world.time:.1f} days; bodies = {world.count}")
        return 0

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
