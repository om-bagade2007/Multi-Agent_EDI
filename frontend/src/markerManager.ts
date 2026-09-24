export type MarkerPosition = [number, number];
export interface KeyedMarker {
  setLngLat(position: MarkerPosition): this;
  remove(): void;
}

/** Create once per key; subsequent coordinate updates use only the map marker API. */
export function updateKeyedMarker<T extends KeyedMarker>(markers: Map<string, T>, id: string, position: MarkerPosition, create: () => T): T {
  const existing = markers.get(id);
  if (existing) return existing.setLngLat(position);
  const marker = create();
  markers.set(id, marker);
  return marker;
}

/** Remove stale entity markers after each keyed snapshot. */
export function removeStaleMarkers<T extends KeyedMarker>(markers: Map<string, T>, keep: (id: string) => boolean): void {
  for (const [id, marker] of markers) if (!keep(id)) { marker.remove(); markers.delete(id); }
}
