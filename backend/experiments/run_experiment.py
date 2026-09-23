"""Run reproducible nearest-baseline episodes and export CSV."""
import argparse
import asyncio
from pathlib import Path

import pandas as pd

from app.sim.manager import SimulationManager


def main() -> None:
    """Parse CLI arguments, execute episodes, and write an experiment table."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="nearest")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seeds", default="1-20")
    parser.add_argument("--duration", type=float, default=3600)
    parser.add_argument("--rate", type=float, default=90, help="Mean incident interval in seconds")
    parser.add_argument("--out", default="results/nearest.csv")
    args = parser.parse_args()
    if args.strategy != "nearest":
        parser.error("Only nearest is implemented in Stage 1")
    start, end = map(int, args.seeds.split("-"))
    rows: list[dict[str, object]] = []
    for seed in list(range(start, end + 1))[:args.episodes]:
        rate_per_minute = 60 / args.rate if args.rate > 0 else 0
        result = asyncio.run(SimulationManager(seed, args.duration, rate_per_minute).run_episode())
        rows.append({"strategy": args.strategy, "seed": seed, **result["metrics"]})
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=["strategy", "seed", "incidents", "avg_response_s", "p95_response_s", "ambulance_util", "fire_util", "police_util", "mean_traffic_delay_s", "queued_end"])
    frame.to_csv(output, index=False)
    print(frame.to_string(index=False))
    print(f"Saved {len(rows)} episode(s) to {output}")


if __name__ == "__main__":
    main()
