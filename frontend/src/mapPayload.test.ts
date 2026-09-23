import { describe, expect, it } from 'vitest';
import { parseFacilities, validPuneCoordinate } from './mapPayload';
import type { PuneNetwork } from './types';

const bbox: PuneNetwork['bbox'] = { south: 18.47, north: 18.58, west: 73.79, east: 73.93 };

describe('Pune coordinate parsing', () => {
  it('accepts only finite nonzero coordinates inside Pune bounds', () => {
    expect(validPuneCoordinate(73.85, 18.52, bbox)).toBe(true);
    expect(validPuneCoordinate(0, 0, bbox)).toBe(false);
    expect(validPuneCoordinate(Number.NaN, 18.52, bbox)).toBe(false);
    expect(validPuneCoordinate(74, 18.52, bbox)).toBe(false);
  });

  it('drops invalid facility records', () => {
    const parsed = parseFacilities([
      { id: 'ok', name: 'Hospital', kind: 'hospital', lat: 18.52, lon: 73.85 },
      { id: 'zero', name: 'Invalid', kind: 'hospital', lat: 0, lon: 0 },
      { id: 'bad', name: 'Invalid', kind: 'police', lat: Infinity, lon: 73.85 },
      { id: 'outside', name: 'Invalid', kind: 'fire_station', lat: 18.7, lon: 73.85 },
    ], bbox);
    expect(parsed.map(item => item.id)).toEqual(['ok']);
  });
});
