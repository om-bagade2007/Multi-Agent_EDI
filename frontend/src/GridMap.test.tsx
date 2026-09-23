import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import GridMap from './GridMap';
import type { Snapshot } from './types';

function fixture(): Snapshot {
  const nodes = Array.from({ length: 25 }, (_, index) => ({ id: `n_${Math.floor(index / 5)}_${index % 5}`, x: index % 5, y: Math.floor(index / 5) }));
  const edges = [];
  for (const node of nodes) {
    if (node.x < 4) edges.push({ id: `${node.id}-right`, from_node: node.id, to_node: `n_${node.y}_${node.x + 1}`, x1: node.x, y1: node.y, x2: node.x + 1, y2: node.y, congestion: 1 });
    if (node.y < 4) edges.push({ id: `${node.id}-down`, from_node: node.id, to_node: `n_${node.y + 1}_${node.x}`, x1: node.x, y1: node.y, x2: node.x, y2: node.y + 1, congestion: 1 });
  }
  return {
    type: 'snapshot', sim_time: 0, units: [], incidents: [], stations: [], hospitals: [], traffic: [],
    road_network: { size: 5, origin_lat: 18.52, origin_lon: 73.85, block_m: 250, nodes, edges },
    agents: {}, metrics: { avg_response_s: 0, traffic_delay_s: 0, queued: 0, response_by_type: {}, utilization: {} },
  } as Snapshot;
}

describe('GridMap road geometry', () => {
  it('renders every 5x5 grid segment from its explicit endpoints', () => {
    const html = renderToStaticMarkup(<GridMap snapshot={fixture()} />);
    const lines = [...html.matchAll(/<line\b([^>]*)>/g)].map(match => match[1]);
    expect(lines).toHaveLength(40);
    const starts = new Set<string>();
    for (const attributes of lines) {
      const x1 = Number(attributes.match(/\bx1="([^"]+)"/)?.[1]);
      const y1 = Number(attributes.match(/\by1="([^"]+)"/)?.[1]);
      const x2 = Number(attributes.match(/\bx2="([^"]+)"/)?.[1]);
      const y2 = Number(attributes.match(/\by2="([^"]+)"/)?.[1]);
      expect([x1, y1, x2, y2].every(Number.isFinite)).toBe(true);
      expect(Math.abs(x2 - x1) + Math.abs(y2 - y1)).toBe(1);
      starts.add(`${x1},${y1}`);
    }
    expect(starts.size).toBeGreaterThan(1);
    expect(starts.has('0,0')).toBe(true); // This fixture really contains node n_0_0.
  });

  it('skips malformed roads and reports their id only once', () => {
    const snapshot = fixture();
    snapshot.road_network?.edges.push({ id: 'bad-edge', from_node: 'missing', to_node: 'n_0_0', x1: Number.NaN, y1: 0, x2: 0, y2: 0, congestion: 1 });
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const first = renderToStaticMarkup(<GridMap snapshot={snapshot} />);
    renderToStaticMarkup(<GridMap snapshot={snapshot} />);
    expect([...first.matchAll(/<line\b/g)]).toHaveLength(40);
    expect(error).toHaveBeenCalledTimes(1);
    expect(error).toHaveBeenCalledWith(expect.stringContaining('bad-edge'));
    error.mockRestore();
  });
});
