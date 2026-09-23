import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import GridMap from './GridMap';
import type { Snapshot } from '../types';

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
  it('renders every 5x5 grid segment inside a fixed 1000-unit viewBox', () => {
    const html = renderToStaticMarkup(<GridMap snapshot={fixture()} />);
    expect(html).toContain('viewBox="0 0 1000 1000"');
    const lines = [...html.matchAll(/<line\b([^>]*)>/g)].map(match => match[1]);
    expect(lines).toHaveLength(40);
    const lengths = new Set<string>();
    const starts = new Set<string>();
    for (const attributes of lines) {
      const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map(key => Number(attributes.match(new RegExp(`\\b${key}="([^"]+)"`))?.[1]));
      expect([x1, y1, x2, y2].every(value => Number.isFinite(value) && value >= 0 && value <= 1000)).toBe(true);
      expect(x1 === x2 || y1 === y2).toBe(true);
      lengths.add((Math.abs(x2 - x1) + Math.abs(y2 - y1)).toFixed(1));
      starts.add(`${x1},${y1}`);
    }
    expect(lengths.size).toBe(1);
    expect(starts.size).toBeGreaterThan(10);
  });

  it('keeps unit marker radii within 20 logical units', () => {
    const snapshot = fixture();
    snapshot.units = [{ id: 'unit-1', kind: 'ambulance', location: { lat: 18.52, lon: 73.85 }, status: 'idle', assigned_incident_id: null }];
    snapshot.incidents = [{ id: 'incident-1', type: 'medical', severity: 3, location: { lat: 18.52, lon: 73.85 }, created_at: 0, status: 'pending' }];
    const html = renderToStaticMarkup(<GridMap snapshot={snapshot} />);
    const circles = [...html.matchAll(/<circle\b([^>]*)>/g)].map(match => match[1]).filter(attributes => attributes.includes('class="map-marker"'));
    expect(circles).toHaveLength(1);
    const radius = Number(circles[0].match(/\br="([^"]+)"/)?.[1]);
    expect(Number.isFinite(radius)).toBe(true);
    expect(radius).toBeLessThanOrEqual(20);
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
