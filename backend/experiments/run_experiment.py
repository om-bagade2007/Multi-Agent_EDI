"""Run reproducible single-strategy or paired dispatch experiments."""
import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.sim.manager import SimulationManager
from app.strategies.registry import STRATEGIES

METRICS = ['avg_response_s', 'ambulance_util', 'fire_util', 'police_util', 'mean_traffic_delay_s']

def episode(strategy: str, seed: int, duration: float, rate_s: float) -> dict[str, object]:
    result = asyncio.run(SimulationManager(seed, duration, 60 / rate_s if rate_s > 0 else 0, strategy=STRATEGIES[strategy]()).run_episode())
    metrics = result['metrics']
    return {'strategy': strategy, 'seed': seed, **{key: metrics[key] for key in METRICS}, 'incidents': metrics['incidents'], 'queued_end': metrics['queued_end']}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--strategy', default='nearest', choices=sorted(STRATEGIES))
    parser.add_argument('--episodes', type=int, default=20)
    parser.add_argument('--seeds', default='1-20')
    parser.add_argument('--duration', type=float, default=3600)
    parser.add_argument('--rate', type=float, default=90, help='Mean incident interval in seconds')
    parser.add_argument('--out', default='results/nearest.csv')
    parser.add_argument('--compare', action='store_true')
    parser.add_argument('--scenarios', type=int, default=1)
    args = parser.parse_args()
    start, end = map(int, args.seeds.split('-'))
    seeds = list(range(start, end + 1))
    if args.compare:
        seeds = list(range(start, start + max(1, args.scenarios)))
        rows = [episode(strategy, seed, args.duration, args.rate) for seed in seeds for strategy in ('nearest', 'hungarian')]
        outdir = Path('experiments/results')
        outdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        csv_path, md_path = outdir / f'comparison_{stamp}.csv', outdir / f'comparison_{stamp}.md'
        frame = pd.DataFrame(rows)
        frame.to_csv(csv_path, index=False)
        summary = frame.groupby('strategy')[METRICS].agg(['mean', 'median', 'std']).round(3)
        means = frame.groupby('strategy')[METRICS].mean()
        improvement = (means.loc['nearest', 'avg_response_s'] - means.loc['hungarian', 'avg_response_s']) / max(means.loc['nearest', 'avg_response_s'], 1e-9) * 100
        md_path.write_text(f'# Dispatch comparison ({len(seeds)} paired scenarios)\n\nSeeds: {seeds}\n\n{summary.to_markdown()}\n\nHungarian mean response-time improvement over nearest: {improvement:.2f}%.\n\nCSV: `{csv_path.as_posix()}`\n', encoding='utf-8')
        latest = {'scenarios': len(seeds), 'seeds': seeds, 'improvement_pct': round(float(improvement), 3), 'strategies': {name: {metric: round(float(means.loc[name, metric]), 3) for metric in METRICS} for name in ('nearest', 'hungarian')}}
        (outdir / 'latest_comparison.json').write_text(json.dumps(latest, indent=2), encoding='utf-8')
        print(summary)
        print(f'Saved paired CSV to {csv_path} and report to {md_path}')
        return
    rows = [episode(args.strategy, seed, args.duration, args.rate) for seed in seeds[:args.episodes]]
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=['strategy', 'seed', 'incidents', *METRICS, 'queued_end'])
    frame.to_csv(output, index=False)
    print(frame.to_string(index=False))
    print(f'Saved {len(rows)} episode(s) to {output}')

if __name__ == '__main__':
    main()
