// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

vi.mock('./PuneMap', () => ({ default: () => <div data-testid="pune-map">Pune streets</div> }));
vi.mock('./dev/GridMap', () => ({ default: () => <div data-testid="grid-map">Developer map</div> }));

import App from './App';

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function setup(mode: 'pune' | 'gridsim', networkStatus = 200) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/experiments/latest')) return Promise.resolve(response(null));
    if (url.endsWith('/scenario')) return Promise.resolve(response({ mode, strategies: ['nearest', 'hungarian'], speeds: [1, 5, 10, 30] }));
    if (url.endsWith('/scenario/network')) return Promise.resolve(networkStatus === 200
      ? response(mode === 'pune'
        ? { mode, bbox: { south: 18.47, north: 18.58, west: 73.79, east: 73.93 }, roads: { type: 'FeatureCollection', features: [] } }
        : { mode, size: 2, origin_lat: 18.52, origin_lon: 73.85, block_m: 100, nodes: [], edges: [] })
      : response({ detail: 'Pune network data is unavailable' }, networkStatus));
    if (url.endsWith('/scenario/facilities')) return Promise.resolve(response([{ id: 'h1', name: 'Hospital', kind: 'hospital', lat: 18.52, lon: 73.85 }]));
    return Promise.resolve(response(null));
  }));
}

describe('dashboard mode routing', () => {
  beforeEach(() => {
    class TestResizeObserver { observe() {} unobserve() {} disconnect() {} }
    vi.stubGlobal('ResizeObserver', TestResizeObserver);
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('renders PuneMap when the scenario says Pune', async () => {
    setup('pune');
    render(<App />);
    expect(await screen.findByTestId('pune-map')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Pune Emergency Response Simulation' })).toBeTruthy();
  });

  it('loads GridMap only for developer GridSim mode', async () => {
    setup('gridsim');
    render(<App />);
    expect(await screen.findByTestId('grid-map')).toBeTruthy();
    expect(screen.queryByTestId('pune-map')).toBeNull();
  });

  it('shows the API detail banner after a 503', async () => {
    setup('pune', 503);
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Pune network data is unavailable');
  });
});
