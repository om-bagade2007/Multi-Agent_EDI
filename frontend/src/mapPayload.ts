import type { Facility, PuneNetwork } from './types';

export type RoadFeature = PuneNetwork['roads']['features'][number];
export type RegionPoint = { id: string; x: number; y: number; priority: number };

/** Keep the highest priority region labels and suppress labels within the requested pixel radius. */
export function filterRegionLabels(points: RegionPoint[], radius = 60): string[] {
  const kept: RegionPoint[] = [];
  for (const point of [...points].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id))) {
    if (kept.every(other => Math.hypot(point.x - other.x, point.y - other.y) >= radius)) kept.push(point);
  }
  return kept.map(point => point.id);
}

/** Approximate point-to-road distance in metres over the network's short local segments. */
export function nearestRoadDistanceMeters(lon: number, lat: number, roads: RoadFeature[]): number {
  const scaleX = 111_320 * Math.cos(lat * Math.PI / 180);
  let best = Number.POSITIVE_INFINITY;
  for (const road of roads) {
    const coordinates = road.geometry.coordinates;
    for (let index = 1; index < coordinates.length; index += 1) {
      const [ax, ay] = coordinates[index - 1]; const [bx, by] = coordinates[index];
      const px = (lon - ax) * scaleX; const py = (lat - ay) * 111_320;
      const vx = (bx - ax) * scaleX; const vy = (by - ay) * 111_320;
      const fraction = Math.max(0, Math.min(1, (px * vx + py * vy) / Math.max(.000001, vx * vx + vy * vy)));
      best = Math.min(best, Math.hypot(px - vx * fraction, py - vy * fraction));
      if (best < 1) return best;
    }
  }
  return best;
}

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
