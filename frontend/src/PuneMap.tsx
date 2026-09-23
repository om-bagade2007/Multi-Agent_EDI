import { useEffect, useRef, useState } from 'react';
import maplibregl, { type LayerSpecification, type Map as MapLibreMap, type Marker } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { validPuneCoordinate } from './mapPayload';
import type { Facility, PuneNetwork, Snapshot } from './types';

type Props = { network: PuneNetwork; facilities: Facility[]; snapshot: Snapshot | null };
type Position = { lon: number; lat: number };
const colorByKind: Record<string, string> = { hospital: '#315D5B', fire_station: '#C56A37', police: '#344B68', ambulance: '#315D5B', fire: '#C56A37', police_unit: '#344B68', incident: '#617D98' };

function elementFor(kind: string, label?: string, status?: string): HTMLDivElement {
  const el = document.createElement('div');
  const className = kind === 'incident' ? 'incident-marker' : ['hospital', 'fire_station', 'police'].includes(kind) ? `facility-marker facility-${kind}` : `unit-marker unit-${kind}`;
  el.className = `pune-marker ${className} ${status === 'idle' ? 'idle' : status ? 'busy' : ''}`;
  el.style.setProperty('--marker-color', colorByKind[kind] ?? colorByKind.incident);
  if (label) {
    const digit = document.createElement('span');
    digit.textContent = label;
    el.append(digit);
  }
  el.setAttribute('aria-label', label ? `${kind} ${label}` : kind.replace('_', ' '));
  el.setAttribute('draggable', 'false');
  return el;
}

export default function PuneMap({ network, facilities, snapshot }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Map<string, Marker>>(new Map());
  const animationFrames = useRef<Map<string, number>>(new Map());
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!host.current) return;
    const useTiles = (import.meta.env.VITE_BASEMAP ?? 'none') === 'carto-light';
    const layers: LayerSpecification[] = [{ id: 'light-background', type: 'background', paint: { 'background-color': '#FAFAF8' } }, ...(useTiles ? [{ id: 'carto-light', type: 'raster' as const, source: 'carto-light' }] : [])];
    const map = new maplibregl.Map({
      container: host.current,
      style: {
        version: 8,
        sources: useTiles ? { 'carto-light': { type: 'raster', tiles: ['https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors © CARTO' } } : {},
        layers,
      },
      center: [73.8567, 18.5204], zoom: 11,
      maxBounds: [[network.bbox.west - .02, network.bbox.south - .02], [network.bbox.east + .02, network.bbox.north + .02]],
      dragRotate: false, pitchWithRotate: false, attributionControl: false,
    });
    map.on('load', () => {
      map.addSource('pune-roads', { type: 'geojson', data: network.roads });
      map.addLayer({ id: 'pune-roads', type: 'line', source: 'pune-roads', paint: { 'line-color': '#ADB6BA', 'line-width': ['match', ['get', 'road_class'], 'motorway', 2.5, 'trunk', 2.2, 'primary', 1.8, 'secondary', 1.4, 1] } });
      host.current?.setAttribute('data-roads-ready', 'true');
      map.addSource('pune-routes', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addLayer({ id: 'pune-routes', type: 'line', source: 'pune-routes', paint: { 'line-color': '#617D98', 'line-width': 2, 'line-opacity': .85 } });
      map.fitBounds([[network.bbox.west, network.bbox.south], [network.bbox.east, network.bbox.north]], { padding: 20, duration: 0 });
      for (const facility of facilities) {
        if (!validPuneCoordinate(facility.lon, facility.lat, network.bbox)) continue;
        const marker = new maplibregl.Marker({ element: elementFor(facility.kind) }).setLngLat([facility.lon, facility.lat]).addTo(map);
        markers.current.set(`facility:${facility.id}`, marker);
      }
      setLoaded(true);
    });
    map.on('error', event => {
      const sourceId = 'sourceId' in event ? event.sourceId : undefined;
      if (sourceId !== 'carto-light' || !map.getLayer('carto-light')) return;
      map.removeLayer('carto-light');
      if (map.getSource('carto-light')) map.removeSource('carto-light');
    });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(host.current);
    mapRef.current = map;
    return () => {
      observer.disconnect();
      animationFrames.current.forEach(frame => cancelAnimationFrame(frame));
      animationFrames.current.clear();
      markers.current.forEach(marker => marker.remove());
      markers.current.clear();
      map.remove();
      mapRef.current = null;
    };
  }, [network, facilities]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !snapshot) return;
    const next = new Set<string>();
    const update = (id: string, kind: string, target: Position, label?: string, status?: string) => {
      if (!validPuneCoordinate(target.lon, target.lat, network.bbox)) return;
      next.add(id);
      let marker = markers.current.get(id);
      if (!marker) {
        marker = new maplibregl.Marker({ element: elementFor(kind, label, status) }).setLngLat([target.lon, target.lat]).addTo(map);
        markers.current.set(id, marker);
      } else {
        const element = marker.getElement();
        element.className = elementFor(kind, label, status).className;
        element.style.setProperty('--marker-color', colorByKind[kind] ?? colorByKind.incident);
        if (label && kind === 'incident') element.textContent = label;
        const oldFrame = animationFrames.current.get(id);
        if (oldFrame) cancelAnimationFrame(oldFrame);
        const start = marker.getLngLat();
        const startedAt = performance.now();
        const animate = (now: number) => {
          const progress = Math.min(1, (now - startedAt) / 450);
          marker!.setLngLat([start.lng + (target.lon - start.lng) * progress, start.lat + (target.lat - start.lat) * progress]);
          if (progress < 1) animationFrames.current.set(id, requestAnimationFrame(animate));
          else animationFrames.current.delete(id);
        };
        animationFrames.current.set(id, requestAnimationFrame(animate));
      }
    };
    snapshot.units.forEach(unit => update(`unit:${unit.id}`, unit.kind === 'police' ? 'police_unit' : unit.kind, { lon: unit.location.lon, lat: unit.location.lat }, undefined, unit.status));
    snapshot.incidents.filter(incident => incident.status !== 'resolved').forEach(incident => update(`incident:${incident.id}`, 'incident', { lon: incident.location.lon, lat: incident.location.lat }, String(incident.severity)));
    for (const [id, marker] of markers.current) if (!id.startsWith('facility:') && !next.has(id)) { marker.remove(); markers.current.delete(id); }
    const routeSource = map.getSource('pune-routes') as maplibregl.GeoJSONSource | undefined;
    routeSource?.setData({ type: 'FeatureCollection', features: (snapshot.routes ?? []).filter(route => route.polyline.length > 1 && route.polyline.every(point => validPuneCoordinate(point.lon, point.lat, network.bbox))).map(route => ({ type: 'Feature' as const, properties: { unit_id: route.unit_id }, geometry: { type: 'LineString' as const, coordinates: route.polyline.map(point => [point.lon, point.lat] as [number, number]) } })) });
  }, [snapshot, network, loaded]);

  return <div className="pune-map" ref={host} role="img" aria-label="Pune emergency response map" />;
}
