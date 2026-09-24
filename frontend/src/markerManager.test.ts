import { describe, expect, it, vi } from 'vitest';
import { removeStaleMarkers, updateKeyedMarker, type KeyedMarker } from './markerManager';
import { filterRegionLabels } from './mapPayload';

class MockMarker implements KeyedMarker {
  readonly root = document.createElement('div');
  lastPosition: [number, number] = [0, 0];
  setLngLat = vi.fn((position: [number, number]) => { this.lastPosition = position; return this; });
  remove = vi.fn();
}

describe('keyed map markers', () => {
  it('creates one marker per id and moves existing markers only through setLngLat', () => {
    const markers = new Map<string, MockMarker>();
    const create = vi.fn(() => new MockMarker());
    const marker = updateKeyedMarker(markers, 'incident:I1', [73.85, 18.52], create);
    const transform = marker.root.style.transform;
    updateKeyedMarker(markers, 'incident:I1', [73.86, 18.53], create);
    expect(create).toHaveBeenCalledTimes(1);
    expect(marker.setLngLat).toHaveBeenCalledWith([73.86, 18.53]);
    expect(marker.root.style.transform).toBe(transform);
    expect(marker.root.style.left).toBe('');
    expect(marker.root.style.top).toBe('');
    expect(marker.root.style.position).toBe('');
  });

  it('removes resolved incident markers by their absent snapshot keys', () => {
    const markers = new Map<string, MockMarker>([['incident:I1', new MockMarker()], ['incident:I2', new MockMarker()], ['unit:A1', new MockMarker()]]);
    const resolved = markers.get('incident:I1')!;
    removeStaleMarkers(markers, id => id !== 'incident:I1');
    expect(resolved.remove).toHaveBeenCalledOnce();
    expect(markers.has('incident:I1')).toBe(false);
    expect(markers.has('incident:I2')).toBe(true);
  });

  it('hides labels within 60px of a higher priority region label', () => {
    expect(filterRegionLabels([
      { id: 'quarter', x: 10, y: 10, priority: 1 },
      { id: 'suburb', x: 50, y: 10, priority: 3 },
      { id: 'far', x: 200, y: 10, priority: 1 },
    ], 60)).toEqual(['suburb', 'far']);
  });
});
