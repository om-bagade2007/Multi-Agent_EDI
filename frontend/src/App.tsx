import { useEffect, useState } from 'react';
import Map, { Layer, Marker, Source } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useRunSocket } from './hooks/useRunSocket';
import type { Decision } from './types';

const mapStyle = {
  version: 8 as const,
  sources: {
    osm: {
      type: 'raster' as const,
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster' as const, source: 'osm' }],
};

export default function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const [seed, setSeed] = useState(1);
  const [rate, setRate] = useState(0.67);
  const [speed, setSpeed] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Decision | null>(null);
  const { snapshot, decisions } = useRunSocket(runId);

  useEffect(() => {
    if (snapshot && snapshot.sim_time >= 3600) setBusy(false);
  }, [snapshot]);

  async function start() {
    try {
      setError(null);
      const response = await fetch('http://localhost:8000/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed, incident_rate: rate, duration_s: 3600, speed }),
      });
      if (!response.ok) throw new Error((await response.json() as { detail?: string }).detail ?? 'Could not start run');
      const data = await response.json() as { id: string };
      setRunId(data.id);
      setSelected(null);
      setBusy(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start run');
    }
  }

  async function control(action: string) {
    if (!runId) return;
    try {
      const response = await fetch(`http://localhost:8000/runs/${runId}/${action}`, { method: 'POST' });
      if (!response.ok) throw new Error('Run control failed');
      if (action === 'stop') setBusy(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Run control failed');
    }
  }

  const units = snapshot?.units ?? [];
  const incidents = snapshot?.incidents ?? [];
  const responseSeries = Object.entries(snapshot?.metrics.response_by_type ?? {}).map(([type, response_s]) => ({ type, response_s }));
  const utilization = Object.entries(snapshot?.metrics.utilization ?? {}).map(([kind, value]) => ({ kind, utilization: value * 100 }));
  const clock = snapshot?.sim_time ?? 0;

  return <main>
    <header>
      <div><small>URBAN RESPONSE NETWORK / PUNE</small><h1>Emergency Operations</h1></div>
      <div className="clock">SIM {Math.floor(clock / 60).toString().padStart(2, '0')}:{Math.floor(clock % 60).toString().padStart(2, '0')}</div>
    </header>
    <nav>
      <label>Seed <input type="number" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label>
      <label>Incidents/min <input type="number" step=".1" value={rate} onChange={event => setRate(Number(event.target.value))} /></label>
      <label>Speed <select value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={1}>1×</option><option value={5}>5×</option><option value={20}>20×</option></select></label>
      <button onClick={() => void start()}>Start</button>
      <button disabled={!runId} onClick={() => void control('pause')}>Pause</button>
      <button disabled={!runId} onClick={() => void control('resume')}>Resume</button>
      <button disabled={!runId} onClick={() => void control('stop')}>Stop</button>
      <button onClick={() => { if (runId) void control('stop'); setRunId(null); setSelected(null); setBusy(false); }}>Reset</button>
      <span className="live">● {busy ? 'LIVE' : 'STANDBY'}</span>
    </nav>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="kpis">
      <article><small>AVG RESPONSE</small><b>{((snapshot?.metrics.avg_response_s ?? 0) / 60).toFixed(1)} min</b></article>
      <article><small>ACTIVE INCIDENTS</small><b>{incidents.filter(incident => incident.status !== 'resolved').length}</b></article>
      <article><small>QUEUED</small><b>{snapshot?.metrics.queued ?? 0}</b></article>
      <article><small>TRAFFIC DELAY</small><b>{(snapshot?.metrics.traffic_delay_s ?? 0).toFixed(1)} s</b></article>
    </section>
    <section className="grid">
      <article className="map">
        <h2>Live City Map</h2>
        <Map initialViewState={{ longitude: 73.86, latitude: 18.53, zoom: 12 }} mapStyle={mapStyle}>
          <Source id="roads" type="geojson" data={{
            type: 'FeatureCollection',
            features: (snapshot?.traffic ?? []).map(edge => ({
              type: 'Feature' as const,
              properties: { congestion: edge.congestion },
              geometry: { type: 'LineString' as const, coordinates: edge.geometry.map(point => [point.lon, point.lat]) },
            })),
          }}>
            <Layer id="traffic" type="line" paint={{ 'line-color': ['interpolate', ['linear'], ['get', 'congestion'], 0.35, '#27d7a1', 1, '#ff4d68'], 'line-width': 4, 'line-opacity': 0.65 }} />
          </Source>
          {(snapshot?.stations ?? []).map(station => <Marker key={station.id} longitude={station.location.lon} latitude={station.location.lat}><span className="station">S</span></Marker>)}
          {(snapshot?.hospitals ?? []).map(hospital => <Marker key={hospital.id} longitude={hospital.location.lon} latitude={hospital.location.lat}><span className="hospital">H</span></Marker>)}
          {units.map(unit => <Marker key={unit.id} longitude={unit.location.lon} latitude={unit.location.lat}><span className={`unit ${unit.kind}`}>{unit.kind === 'ambulance' ? '✚' : unit.kind === 'fire' ? '▲' : '●'}</span></Marker>)}
          {incidents.filter(incident => incident.status !== 'resolved').map(incident => <Marker key={incident.id} longitude={incident.location.lon} latitude={incident.location.lat}><span className={`incident s${incident.severity}`}>{incident.severity}</span></Marker>)}
        </Map>
      </article>
      <aside>
        <article><h2>Response Agents</h2>{['ambulance', 'fire', 'police'].map(kind => <div className="agent-card" key={kind}><div className="resource"><span>{kind}</span><b>{snapshot?.agents[kind]?.idle ?? units.filter(unit => unit.kind === kind && unit.status === 'idle').length} idle</b><small>{snapshot?.agents[kind]?.busy ?? units.filter(unit => unit.kind === kind && unit.status !== 'idle').length} busy</small></div><p>{snapshot?.agents[kind]?.last_action ?? 'Standing by'}</p></div>)}<div className="agent-card"><div className="resource"><span>hospital</span><b>{snapshot?.agents.hospital?.beds_free ?? 65} beds</b><small>{snapshot?.agents.hospital?.icu_free ?? 15} ICU</small></div><p>{snapshot?.agents.hospital?.last_action ?? 'Standing by'}</p></div></article>
        <article><h2>Active Incidents</h2>{incidents.filter(incident => incident.status !== 'resolved').slice(-8).map(incident => <div className="resource" key={incident.id}><span>{incident.id} · {incident.type}</span><b className={`sev s${incident.severity}`}>SEV {incident.severity}</b><small>{incident.status}</small></div>)}</article>
        <article>
          <h2>Recent Decisions</h2>
          {decisions.slice(0, 5).map((decision, index) => <button className="decision" key={`${decision.incident_id}-${index}`} onClick={() => setSelected(decision)}>{decision.explanation}</button>)}
          {selected && <div className="candidate-detail"><p>{selected.incident_id} · {selected.unit_id} · ETA {(selected.eta_s / 60).toFixed(1)} min</p><table><thead><tr><th>Unit</th><th>ETA</th><th>Distance</th></tr></thead><tbody>{(selected.candidates ?? []).map(candidate => <tr key={candidate.unit_id}><td>{candidate.unit_id}{candidate.unit_id === selected.unit_id ? ' ✓' : ''}</td><td>{(candidate.eta_s / 60).toFixed(1)} min</td><td>{candidate.distance_m.toFixed(0)} m</td></tr>)}</tbody></table></div>}
        </article>
        <article><h2>Average Response by Type</h2><ResponsiveContainer width="100%" height={150}><LineChart data={responseSeries}><CartesianGrid strokeDasharray="3 3" stroke="#26334a" /><XAxis dataKey="type" stroke="#8594ae" /><YAxis stroke="#8594ae" /><Tooltip /><Line dataKey="response_s" stroke="#44d6a3" /></LineChart></ResponsiveContainer></article>
        <article><h2>Resource Utilisation</h2><ResponsiveContainer width="100%" height={150}><BarChart data={utilization}><CartesianGrid strokeDasharray="3 3" stroke="#26334a" /><XAxis dataKey="kind" stroke="#8594ae" /><YAxis stroke="#8594ae" /><Tooltip /><Bar dataKey="utilization" fill="#44d6a3" /></BarChart></ResponsiveContainer></article>
      </aside>
    </section>
  </main>;
}
