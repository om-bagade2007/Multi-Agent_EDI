import { useEffect, useRef, useState } from 'react';
import maplibregl, { type LayerSpecification, type Map as MapLibreMap, type Marker } from 'maplibre-gl';
import type { FeatureCollection, Geometry } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import { filterRegionLabels, nearestRoadDistanceMeters, validPuneCoordinate } from './mapPayload';
import { removeStaleMarkers, updateKeyedMarker } from './markerManager';
import type { Facility, PuneNetwork, PuneRegions, Snapshot } from './types';

type Props = { network: PuneNetwork; facilities: Facility[]; snapshot: Snapshot | null; regions: PuneRegions; showRegions: boolean };
type Position = { lon: number; lat: number };
type Motion = { marker: Marker; start: Position; target: Position; elapsed: number; last: number | null };
const colorByKind: Record<string, string> = { hospital: '#315D5B', fire_station: '#C56A37', police: '#344B68', ambulance: '#315D5B', fire: '#C56A37', police_unit: '#344B68', incident: '#617D98' };
const emptyRegions: FeatureCollection<Geometry> = { type: 'FeatureCollection', features: [] };

function markerElement(kind: string, label?: string, status?: string): HTMLDivElement {
  const root = document.createElement('div');
  root.setAttribute('aria-label', label ? `${kind} ${label}` : kind.replace('_', ' '));
  root.setAttribute('draggable', 'false');
  const visual = document.createElement('div');
  const className = kind === 'incident' ? 'incident-marker' : ['hospital', 'fire_station', 'police'].includes(kind) ? `facility-marker facility-${kind}` : `unit-marker unit-${kind}`;
  visual.className = `pune-marker ${className} ${status === 'idle' ? 'idle' : status ? 'busy' : ''}`;
  visual.style.setProperty('--marker-color', colorByKind[kind] ?? colorByKind.incident);
  if (label) {
    const digit = document.createElement('span');
    digit.textContent = label;
    visual.append(digit);
  }
  root.append(visual);
  return root;
}

export default function PuneMap({ network, facilities, snapshot, regions, showRegions }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Map<string, Marker>>(new Map());
  const animationFrames = useRef<Map<string, number>>(new Map());
  const motions = useRef<Map<string, Motion>>(new Map());
  const scheduleMotionRef = useRef<(id: string) => void>(() => undefined);
  const [loaded, setLoaded] = useState(false);
  const [basemapFailed, setBasemapFailed] = useState(false);

  useEffect(() => {
    if (!host.current) return;
    const mode = import.meta.env.VITE_BASEMAP ?? 'carto-light';
    const baseTiles = mode === 'osm'
      ? ['https://tile.openstreetmap.org/{z}/{x}/{y}.png']
      : ['a', 'b', 'c', 'd'].map(subdomain => `https://${subdomain}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png`);
    const labelTiles = ['a', 'b', 'c', 'd'].map(subdomain => `https://${subdomain}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png`);
    const useTiles = mode !== 'none';
    const useCarto = useTiles && mode !== 'osm';
    const sources = useTiles ? {
      'carto-base': { type: 'raster' as const, tiles: baseTiles, tileSize: 256, maxzoom: 19, attribution: mode === 'osm' ? '© OpenStreetMap contributors' : '© OpenStreetMap contributors © CARTO' },
      ...(useCarto ? { 'carto-labels': { type: 'raster' as const, tiles: labelTiles, tileSize: 256, maxzoom: 19, attribution: '© OpenStreetMap contributors © CARTO' } } : {}),
    } : {};
    const layers: LayerSpecification[] = [
      { id: 'bg', type: 'background', paint: { 'background-color': '#FAFAF8' } },
      ...(useTiles ? [{ id: 'carto-base', type: 'raster' as const, source: 'carto-base' }] : []),
      ...(useCarto ? [{ id: 'carto-labels', type: 'raster' as const, source: 'carto-labels' }] : []),
    ];
    const map = new maplibregl.Map({
      container: host.current,
      style: { version: 8, sources, layers },
      center: [73.8567, 18.5204], zoom: 11,
      maxBounds: [[network.bbox.west - .02, network.bbox.south - .02], [network.bbox.east + .02, network.bbox.north + .02]],
      dragRotate: false, pitchWithRotate: false, attributionControl: false,
    });
    map.on('load', () => {
      map.addSource('pune-regions', { type: 'geojson', data: (regions.available ? regions : emptyRegions) as unknown as FeatureCollection<Geometry> });
      map.addLayer({ id: 'pune-water', type: 'fill', source: 'pune-regions', filter: ['all', ['==', ['geometry-type'], 'Polygon'], ['==', ['get', 'kind'], 'water']], paint: { 'fill-color': '#DCE6EC', 'fill-opacity': .8 } });
      map.addLayer({ id: 'pune-park', type: 'fill', source: 'pune-regions', filter: ['all', ['==', ['geometry-type'], 'Polygon'], ['==', ['get', 'kind'], 'park']], paint: { 'fill-color': '#E3EBDD', 'fill-opacity': .8 } });
      map.addLayer({ id: 'pune-water-lines', type: 'line', source: 'pune-regions', filter: ['all', ['==', ['geometry-type'], 'LineString'], ['==', ['get', 'kind'], 'water']], paint: { 'line-color': '#DCE6EC', 'line-width': 2 } });
      map.addSource('pune-roads', { type: 'geojson', data: network.roads });
      map.addLayer({ id: 'pune-roads', type: 'line', source: 'pune-roads', minzoom: 10, paint: { 'line-color': '#AEBCC3', 'line-width': ['match', ['get', 'road_class'], 'motorway', 2.5, 'trunk', 2.2, 'primary', 1.8, 'secondary', 1.4, 1] } });
      if (useCarto) map.moveLayer('carto-labels');
      map.addSource('pune-routes', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addLayer({ id: 'pune-routes', type: 'line', source: 'pune-routes', paint: { 'line-color': '#617D98', 'line-width': 2, 'line-opacity': .85 } });
      host.current?.setAttribute('data-roads-ready', 'true');
      map.fitBounds([[network.bbox.west, network.bbox.south], [network.bbox.east, network.bbox.north]], { padding: 20, duration: 0 });
      facilities.forEach(facility => {
        if (!validPuneCoordinate(facility.lon, facility.lat, network.bbox)) return;
        updateKeyedMarker(markers.current, `facility:${facility.id}`, [facility.lon, facility.lat], () => new maplibregl.Marker({ element: markerElement(facility.kind), anchor: 'center' }).setLngLat([facility.lon, facility.lat]).addTo(map));
      });
      setLoaded(true);
    });
    map.on('sourcedata', event => {
      if (event.sourceId === 'pune-roads' && event.isSourceLoaded) host.current?.setAttribute('data-roads-loaded', 'true');
    });
    const tileErrors = new Map<string, number>();
    map.on('error', event => {
      const sourceId = 'sourceId' in event ? event.sourceId : undefined;
      if (sourceId !== 'carto-base' && sourceId !== 'carto-labels') return;
      const count = (tileErrors.get(sourceId) ?? 0) + 1;
      tileErrors.set(sourceId, count);
      if (count >= 3) setBasemapFailed(true);
    });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(host.current);
    const visibility = () => {
      if (document.hidden) {
        animationFrames.current.forEach(frame => cancelAnimationFrame(frame));
        animationFrames.current.clear();
        motions.current.forEach(motion => { motion.last = null; });
      } else {
        motions.current.forEach((_, id) => scheduleMotionRef.current(id));
      }
    };
    function scheduleMotion(id: string) {
      const motion = motions.current.get(id);
      if (!motion || document.hidden || animationFrames.current.has(id)) return;
      const frame = requestAnimationFrame(now => {
        animationFrames.current.delete(id);
        const active = motions.current.get(id);
        if (!active) return;
        if (active.last !== null) active.elapsed += Math.min(now - active.last, 50);
        active.last = now;
        const progress = Math.min(1, active.elapsed / 450);
        active.marker.setLngLat([active.start.lon + (active.target.lon - active.start.lon) * progress, active.start.lat + (active.target.lat - active.start.lat) * progress]);
        if (progress < 1) scheduleMotion(id);
        else motions.current.delete(id);
      });
      animationFrames.current.set(id, frame);
    }
    scheduleMotionRef.current = scheduleMotion;
    document.addEventListener('visibilitychange', visibility);
    if (import.meta.env.MODE === 'test' || import.meta.env.VITE_EXPOSE_MAP === '1') window.__puneMap = map;
    map.on('remove', () => { if (window.__puneMap === map) delete window.__puneMap; });
    mapRef.current = map;
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      observer.disconnect();
      animationFrames.current.forEach(frame => cancelAnimationFrame(frame));
      animationFrames.current.clear();
      motions.current.clear();
      markers.current.forEach(marker => marker.remove());
      markers.current.clear();
      map.remove();
      mapRef.current = null;
      scheduleMotionRef.current = () => undefined;
      setLoaded(false);
    };
  }, [network, facilities]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const regionFeatures = regions.available ? regions.features : [];
    const source = map.getSource('pune-regions') as maplibregl.GeoJSONSource | undefined;
    source?.setData((regions.available ? regions : emptyRegions) as unknown as FeatureCollection<Geometry>);
    for (const id of ['pune-water', 'pune-park', 'pune-water-lines']) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', showRegions ? 'visible' : 'none');
    const names = regionFeatures.filter(feature => feature.properties.name && ['suburb', 'neighbourhood', 'quarter'].includes(feature.properties.kind ?? '') && feature.geometry.type === 'Point');
    const seen = new Set<string>();
    names.forEach((feature, index) => {
      const id = `region:${feature.id ?? `${feature.properties.kind}:${feature.properties.name}:${index}`}`;
      seen.add(id);
      const coords = feature.geometry.coordinates as [number, number];
      let marker = markers.current.get(id);
      if (!marker) {
        const root = document.createElement('div');
        const label = document.createElement('span');
        label.className = 'region-label'; label.dataset.regionLabel = 'true'; label.textContent = feature.properties.name ?? '';
        root.append(label);
        marker = new maplibregl.Marker({ element: root, anchor: 'center' }).setLngLat(coords).addTo(map);
        markers.current.set(id, marker);
      } else marker.setLngLat(coords);
    });
    for (const [id, marker] of markers.current) if (id.startsWith('region:') && !seen.has(id)) { marker.remove(); markers.current.delete(id); }
    const updateCollisions = () => {
      const points = [...markers.current.entries()].filter(([id]) => id.startsWith('region:')).map(([id, marker]) => {
        const feature = regionFeatures.find((item, index) => id === `region:${item.id ?? `${item.properties.kind}:${item.properties.name}:${index}`}`);
        const coord = marker.getLngLat();
        const zoomVisible = map.getZoom() >= (feature?.properties.kind === 'suburb' ? 11.5 : 13);
        marker.getElement().firstElementChild?.classList.toggle('region-hidden', !showRegions || !zoomVisible);
        return { id, x: map.project(coord).x, y: map.project(coord).y, priority: feature?.properties.kind === 'suburb' ? 3 : feature?.properties.kind === 'neighbourhood' ? 2 : 1 };
      });
      const visible = new Set(filterRegionLabels(points, 60));
      for (const [id, marker] of markers.current) if (id.startsWith('region:')) marker.getElement().firstElementChild?.classList.toggle('region-hidden', !visible.has(id) || !showRegions);
    };
    map.on('moveend', updateCollisions);
    updateCollisions();
    return () => { map.off('moveend', updateCollisions); };
  }, [regions, showRegions, loaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    if (!snapshot) {
      for (const [id, marker] of markers.current) if (!id.startsWith('facility:') && !id.startsWith('region:')) { marker.remove(); markers.current.delete(id); motions.current.delete(id); }
      const source = map.getSource('pune-routes') as maplibregl.GeoJSONSource | undefined;
      source?.setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const next = new Set<string>();
    const update = (id: string, kind: string, target: Position, label?: string, status?: string) => {
      if (!validPuneCoordinate(target.lon, target.lat, network.bbox)) return;
      next.add(id);
      let marker = markers.current.get(id);
      if (!marker) {
        marker = updateKeyedMarker(markers.current, id, [target.lon, target.lat], () => new maplibregl.Marker({ element: markerElement(kind, label, status), anchor: 'center' }).setLngLat([target.lon, target.lat]).addTo(map));
      } else {
        const child = marker.getElement().firstElementChild as HTMLDivElement | null;
        if (child) {
          const className = kind === 'incident' ? 'incident-marker' : ['hospital', 'fire_station', 'police'].includes(kind) ? `facility-marker facility-${kind}` : `unit-marker unit-${kind}`;
          child.className = `pune-marker ${className} ${status === 'idle' ? 'idle' : status ? 'busy' : ''}`;
          child.style.setProperty('--marker-color', colorByKind[kind] ?? colorByKind.incident);
          if (kind === 'incident' && label) child.firstElementChild!.textContent = label;
        }
        const oldFrame = animationFrames.current.get(id);
        if (oldFrame) cancelAnimationFrame(oldFrame);
        animationFrames.current.delete(id);
        const start = marker.getLngLat();
        motions.current.set(id, { marker, start: { lon: start.lng, lat: start.lat }, target, elapsed: 0, last: null });
        scheduleMotionRef.current(id);
      }
    };
    snapshot.units.forEach(unit => update(`unit:${unit.id}`, unit.kind === 'police' ? 'police_unit' : unit.kind, { lon: unit.location.lon, lat: unit.location.lat }, undefined, unit.status));
    snapshot.incidents.filter(incident => incident.status !== 'resolved').forEach(incident => update(`incident:${incident.id}`, 'incident', { lon: incident.location.lon, lat: incident.location.lat }, String(incident.severity)));
    removeStaleMarkers(markers.current, id => !id.startsWith('unit:') && !id.startsWith('incident:') || next.has(id));
    for (const id of motions.current.keys()) if (!next.has(id)) motions.current.delete(id);
    const routeSource = map.getSource('pune-routes') as maplibregl.GeoJSONSource | undefined;
    routeSource?.setData({ type: 'FeatureCollection', features: (snapshot.routes ?? []).filter(route => route.polyline.length > 1 && route.polyline.every(point => validPuneCoordinate(point.lon, point.lat, network.bbox))).map(route => ({ type: 'Feature' as const, properties: { unit_id: route.unit_id }, geometry: { type: 'LineString' as const, coordinates: route.polyline.map(point => [point.lon, point.lat] as [number, number]) } })) });
    if (import.meta.env.DEV) for (const incident of snapshot.incidents.filter(item => item.status !== 'resolved')) {
      const distance = nearestRoadDistanceMeters(incident.location.lon, incident.location.lat, network.roads.features);
      if (distance > 30) console.warn(`Incident ${incident.id} is ${distance.toFixed(1)} m from the nearest displayed road.`);
    }
  }, [snapshot, network, loaded]);

  return <div className="pune-map-shell"><div className="pune-map" ref={host} role="img" aria-label="Pune emergency response map" />{basemapFailed && <div className="map-basemap-notice" role="status">Basemap unavailable. Showing roads only.</div>}</div>;
}
