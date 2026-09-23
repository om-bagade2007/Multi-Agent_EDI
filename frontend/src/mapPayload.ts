import type { Facility, PuneNetwork } from './types';

/** Reject malformed, non-finite, out-of-bounds, and (0,0) map coordinates. */
export function validPuneCoordinate(lon: number, lat: number, bbox: PuneNetwork['bbox']): boolean {
  return Number.isFinite(lon) && Number.isFinite(lat) && lon !== 0 && lat !== 0 && lon >= bbox.west && lon <= bbox.east && lat >= bbox.south && lat <= bbox.north;
}

/** Parse facility payloads defensively so invalid locations are never mapped. */
export function parseFacilities(value: unknown, bbox: PuneNetwork['bbox']): Facility[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Facility => {
    if (typeof item !== 'object' || item === null) return false;
    const facility = item as Partial<Facility>;
    return typeof facility.id === 'string' && typeof facility.name === 'string' && ['hospital', 'fire_station', 'police'].includes(String(facility.kind)) && typeof facility.lon === 'number' && typeof facility.lat === 'number' && validPuneCoordinate(facility.lon, facility.lat, bbox);
  });
}
