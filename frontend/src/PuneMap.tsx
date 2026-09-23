import { useEffect, useRef } from 'react';
import maplibregl, { type Map as MapLibreMap, type Marker } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Incident, PuneNetwork, Snapshot } from './types';

type Props = { network: PuneNetwork; snapshot: Snapshot | null };
const colors: Record<string, string> = { hospital: '#315D5B', fire_station: '#C56A37', police: '#344B68', ambulance: '#315D5B', fire: '#C56A37', police_unit: '#344B68', incident: '#617D98' };
const initialPosition: [number, number] = [73.8567, 18.5204];

function valid(lon: number, lat: number, box: PuneNetwork['bbox']): boolean {
  return Number.isFinite(lon) && Number.isFinite(lat) && lon !== 0 && lat !== 0 && lon >= box.west && lon <= box.east && lat >= box.south && lat <= box.north;
}

function markerElement(kind: string, label?: string, status?: string): HTMLDivElement {
  const el = document.createElement('div');
  el.className = `pune-marker ${kind.startsWith('incident') ? 'incident-marker' : kind.includes('station') || kind === 'hospital' ? 'square-marker' : 'unit-marker'} ${status === 'idle' ? 'idle-marker' : ''}`;
  el.style.backgroundColor = colors[kind] ?? colors.incident;
  if (label) el.textContent = label;
  el.setAttribute('aria-label', label ? `${kind} ${label}` : kind);
  el.setAttribute('draggable', 'false');
  return el;
}

export default function PuneMap({ network, snapshot }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef<Map<string, Marker>>(new Map());
  useEffect(() => {
    if (!host.current) return;
    const useTiles = (import.meta.env.VITE_BASEMAP ?? 'carto-light') === 'carto-light';
    const instance = new maplibregl.Map({
      container: host.current,
      style: { version: 8, sources: useTiles ? { 'carto-light': { type: 'raster', tiles: ['https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors © CARTO' } } : {}, layers: useTiles ? [{ id: 'carto-light', type: 'raster', source: 'carto-light' }] : [] },
      center: initialPosition, zoom: 11, maxBounds: [[network.bbox.west - .02, network.bbox.south - .02], [network.bbox.east + .02, network.bbox.north + .02]],
      dragRotate: false, pitchWithRotate: false, attributionControl: false,
    });
    instance.addControl(new maplibregl.AttributionControl({ compact: true }));
    instance.on('load', () => {
      instance.addSource('pune-roads', { type: 'geojson', data: network.roads });
      instance.addLayer({ id: 'pune-roads', type: 'line', source: 'pune-roads', paint: { 'line-color': '#ADB6BA', 'line-width': ['match', ['get', 'road_class'], 'motorway', 2.5, 'trunk', 2.2, 'primary', 1.8, 'secondary', 1.4, 1] } });
      instance.fitBounds([[network.bbox.west, network.bbox.south], [network.bbox.east, network.bbox.north]], { padding: 20, duration: 0 });
      for (const poi of network.pois) if (valid(poi.lon, poi.lat, network.bbox)) {
        const marker = new maplibregl.Marker({ element: markerElement(poi.kind) }).setLngLat([poi.lon, poi.lat]).addTo(instance);
        markers.current.set(`poi:${poi.id}`, marker);
      }
    });
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(host.current);
    map.current = instance;
    return () => { observer.disconnect(); markers.current.forEach(marker => marker.remove()); markers.current.clear(); instance.remove(); map.current = null; };
  }, [network]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !snapshot) return;
    const next = new Set<string>();
    const put = (id: string, kind: string, lon: number, lat: number, label?: string, status?: string) => {
      if (!valid(lon, lat, network.bbox)) return;
      next.add(id);
      const existing = markers.current.get(id);
      if (existing) existing.setLngLat([lon, lat]);
      else markers.current.set(id, new maplibregl.Marker({ element: markerElement(kind, label, status) }).setLngLat([lon, lat]).addTo(instance));
    };
    snapshot.units.forEach(unit => put(`unit:${unit.id}`, unit.kind === 'police' ? 'police_unit' : unit.kind, unit.location.lon, unit.location.lat, undefined, unit.status));
    snapshot.incidents.filter((incident: Incident) => incident.status !== 'resolved').forEach(incident => put(`incident:${incident.id}`, 'incident', incident.location.lon, incident.location.lat, String(incident.severity)));
    for (const [id, marker] of markers.current) if (!id.startsWith('poi:') && !next.has(id)) { marker.remove(); markers.current.delete(id); }
  }, [snapshot, network]);

  return <div className="pune-map" ref={host} role="img" aria-label="Pune emergency response map" />;
}
