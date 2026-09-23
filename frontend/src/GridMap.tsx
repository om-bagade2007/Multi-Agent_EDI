import { useEffect, useMemo, useRef, useState } from 'react';
import type { Coord, GridEdge, GridNode, GridRoadNetwork, Snapshot } from './types';

type Props = { snapshot: Snapshot | null };
type Point = { x: number; y: number };
const invalidLogged = new Set<string>();
const paddingPx = 18;

function reportInvalid(id: string, reason: string) {
  if (invalidLogged.has(id)) return;
  invalidLogged.add(id);
  console.error(`Skipping invalid map item ${id}: ${reason}`);
}

function finitePoint(point: Point): boolean {
  return Number.isFinite(point.x) && Number.isFinite(point.y);
}

function gridPosition(location: Coord, network: GridRoadNetwork, id: string): Point | null {
  if (!Number.isFinite(location.lat) || !Number.isFinite(location.lon)) {
    reportInvalid(id, 'location coordinates are not finite');
    return null;
  }
  const latStep = network.block_m / 111_320;
  const lonStep = network.block_m / (111_320 * Math.cos(network.origin_lat * Math.PI / 180));
  const x = Math.round((location.lon - network.origin_lon) / lonStep);
  const y = Math.round((location.lat - network.origin_lat) / latStep);
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    reportInvalid(id, 'location cannot be mapped to grid coordinates');
    return null;
  }
  // Match GridSim._node: off-grid entities use their nearest in-bounds intersection.
  return { x: Math.max(0, Math.min(network.size - 1, x)), y: Math.max(0, Math.min(network.size - 1, y)) };
}

function shapePath(point: Point, radius: number): string {
  return `M ${point.x} ${point.y - radius} L ${point.x + radius} ${point.y} L ${point.x} ${point.y + radius} L ${point.x - radius} ${point.y} Z`;
}

export default function GridMap({ snapshot }: Props) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState({ width: 0, height: 0 });
  const network = snapshot?.road_network;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      setViewport(current => current.width === width && current.height === height ? current : { width, height });
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  const valid = useMemo(() => {
    if (!snapshot) return { nodes: [] as GridNode[], edges: [] as GridEdge[] };
    if (!network) {
      reportInvalid('road_network', 'network payload is missing');
      return { nodes: [] as GridNode[], edges: [] as GridEdge[] };
    }
    const nodes = network.nodes.filter(node => {
      if (finitePoint(node)) return true;
      reportInvalid(node.id, 'node coordinates are not finite');
      return false;
    });
    const nodeById = new Map(nodes.map(node => [node.id, node]));
    const edges = network.edges.filter(edge => {
      const from = nodeById.get(edge.from_node);
      const to = nodeById.get(edge.to_node);
      const coordinatesValid = [edge.x1, edge.y1, edge.x2, edge.y2].every(Number.isFinite);
      if (from && to && coordinatesValid && from.x === edge.x1 && from.y === edge.y1 && to.x === edge.x2 && to.y === edge.y2) return true;
      reportInvalid(edge.id, 'edge has invalid coordinates or references an unknown/mismatched node');
      return false;
    });
    return { nodes, edges };
  }, [network, snapshot]);

  const bounds = valid.nodes.length ? {
    minX: Math.min(...valid.nodes.map(node => node.x)), maxX: Math.max(...valid.nodes.map(node => node.x)),
    minY: Math.min(...valid.nodes.map(node => node.y)), maxY: Math.max(...valid.nodes.map(node => node.y)),
  } : { minX: 0, maxX: 1, minY: 0, maxY: 1 };
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanY = Math.max(1, bounds.maxY - bounds.minY);
  const scale = viewport.width > 0 && viewport.height > 0
    ? Math.max(0.001, Math.min((viewport.width - 2 * paddingPx) / spanX, (viewport.height - 2 * paddingPx) / spanY))
    : 1;
  const viewWidth = viewport.width > 0 ? viewport.width / scale : spanX + 1;
  const viewHeight = viewport.height > 0 ? viewport.height / scale : spanY + 1;
  const viewX = (bounds.minX + bounds.maxX - viewWidth) / 2;
  const viewY = (bounds.minY + bounds.maxY - viewHeight) / 2;
  const strokeWidth = 2 / scale;
  const nodeRadius = 2.5 / scale;
  const markerHalf = 5 / scale;
  const locationPoint = (coord: Coord, id: string) => network ? gridPosition(coord, network, id) : null;

  return <div className="map-canvas" ref={canvasRef}>
    <svg className="grid-map" viewBox={`${viewX} ${viewY} ${viewWidth} ${viewHeight}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="GridSim road network">
      <rect x={viewX} y={viewY} width={viewWidth} height={viewHeight} fill="var(--surface)" />
      {valid.edges.map(edge => <line key={edge.id} x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} stroke="var(--road)" strokeWidth={strokeWidth} />)}
      {valid.nodes.map(node => <circle key={node.id} cx={node.x} cy={node.y} r={nodeRadius} fill="var(--surface)" stroke="var(--road-node)" strokeWidth={strokeWidth} />)}
      {snapshot?.stations.map(station => {
        const point = locationPoint(station.location, station.id);
        return point && <rect key={station.id} x={point.x - markerHalf} y={point.y - markerHalf} width={markerHalf * 2} height={markerHalf * 2} fill="var(--accent)" />;
      })}
      {snapshot?.hospitals.map(hospital => {
        const point = locationPoint(hospital.location, hospital.id);
        return point && <rect key={hospital.id} x={point.x - markerHalf} y={point.y - markerHalf} width={markerHalf * 2} height={markerHalf * 2} fill="var(--surface)" stroke="var(--accent)" strokeWidth={strokeWidth} />;
      })}
      {snapshot?.units.map(unit => {
        const point = locationPoint(unit.location, unit.id);
        return point && <circle key={unit.id} cx={point.x} cy={point.y} r={markerHalf} fill="var(--accent)" />;
      })}
      {snapshot?.incidents.filter(incident => incident.status !== 'resolved').map(incident => {
        const point = locationPoint(incident.location, incident.id);
        return point && <g key={incident.id}><path d={shapePath(point, markerHalf)} fill="var(--text)" /><text x={point.x} y={point.y + markerHalf * .3} textAnchor="middle" className="map-label">{incident.severity}</text></g>;
      })}
    </svg>
  </div>;
}
