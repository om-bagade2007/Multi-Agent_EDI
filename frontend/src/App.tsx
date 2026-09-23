import { lazy, Suspense, useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import PuneMap from './PuneMap';
import { parseFacilities } from './mapPayload';
import { assertNoGridTiles } from './lib/mapMode';
import { useRunSocket } from './hooks/useRunSocket';
import type { Comparison, Decision, Facility, GridRoadNetwork, PuneNetwork } from './types';

const GridMap = lazy(() => import('./dev/GridMap'));
assertNoGridTiles(import.meta.env.VITE_SIMULATION_MODE ?? 'pune', []);

export default function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const [seed, setSeed] = useState(1);
  const [rate, setRate] = useState(0.67);
  const [speed, setSpeed] = useState(1);
  const [strategy, setStrategy] = useState('nearest');
  const [strategies, setStrategies] = useState<string[]>(['nearest', 'hungarian']);
  const [speedOptions, setSpeedOptions] = useState<number[]>([1, 5, 10, 30]);
  const [mode, setMode] = useState(import.meta.env.VITE_SIMULATION_MODE ?? 'pune');
  const [scenarioLoaded, setScenarioLoaded] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [baseNetwork, setBaseNetwork] = useState<GridRoadNetwork | null>(null);
  const [puneNetwork, setPuneNetwork] = useState<PuneNetwork | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Decision | null>(null);
  const { snapshot, decisions } = useRunSocket(runId);

  useEffect(() => {
    if (snapshot && snapshot.sim_time >= 3600) setBusy(false);
  }, [snapshot]);

  useEffect(() => {
    const refresh = () => { void fetch('/api/experiments/latest').then(response => response.ok ? response.json() : null).then(data => setComparison(data as Comparison | null)).catch(() => setComparison(null)); };
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void fetch('/api/scenario').then(async response => {
      if (!response.ok) throw new Error(`Scenario service returned HTTP ${response.status}`);
      return response.json();
    }).then(data => {
      const nextMode = data?.mode === 'gridsim' ? 'gridsim' : 'pune';
      setMode(nextMode);
      if (data?.dispatch_strategy) setStrategy(data.dispatch_strategy as string);
      if (Array.isArray(data?.speeds)) setSpeedOptions(data.speeds as number[]);
      if (Array.isArray(data?.strategies)) setStrategies(data.strategies as string[]);
      setScenarioLoaded(true);
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Simulation API is unavailable.'));
  }, []);

  useEffect(() => {
    if (!scenarioLoaded) return;
    const loadNetwork = async () => {
      const networkResponse = await fetch('/api/scenario/network');
      if (!networkResponse.ok) {
        const detail = await networkResponse.json().catch(() => ({})) as { detail?: string };
        throw new Error(detail.detail ?? `Network service returned HTTP ${networkResponse.status}`);
      }
      const networkData = await networkResponse.json();
      if (mode === 'pune') {
        setPuneNetwork(networkData as PuneNetwork);
        const facilitiesResponse = await fetch('/api/scenario/facilities');
        if (!facilitiesResponse.ok) {
          const detail = await facilitiesResponse.json().catch(() => ({})) as { detail?: string };
          throw new Error(detail.detail ?? `Facilities service returned HTTP ${facilitiesResponse.status}`);
        }
        setFacilities(parseFacilities(await facilitiesResponse.json(), (networkData as PuneNetwork).bbox));
      } else {
        setBaseNetwork(networkData as GridRoadNetwork);
      }
    };
    void loadNetwork().catch(cause => setError(cause instanceof Error ? cause.message : 'Pune network is unavailable.'));
  }, [mode, scenarioLoaded]);

  useEffect(() => { document.title = mode === 'pune' ? 'Pune Emergency Response Simulation' : 'Emergency Response Simulation'; }, [mode]);

  async function start() {
    try {
      setError(null);
      const response = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed, incident_rate: rate, duration_s: 3600, speed, strategy }),
      });
      if (!response.ok) {
        if (response.status >= 500) throw new Error('Simulation API is unavailable. Start the backend server; see the README run instructions.');
        throw new Error((await response.json() as { detail?: string }).detail ?? 'Could not start run');
      }
      const data = await response.json() as { id: string };
      setRunId(data.id);
      setSelected(null);
      setBusy(true);
    } catch (cause) {
      setError(cause instanceof TypeError ? 'Cannot reach the simulation API. Start the backend server; see the README run instructions.' : cause instanceof Error ? cause.message : 'Could not start run');
    }
  }

  async function control(action: string) {
    if (!runId) return;
    try {
      const response = await fetch(`/api/runs/${runId}/${action}`, { method: 'POST' });
      if (!response.ok) throw new Error(response.status >= 500 ? 'Simulation API is unavailable. Start the backend server; see the README run instructions.' : 'Run control failed');
      if (action === 'stop') setBusy(false);
    } catch (cause) {
      setError(cause instanceof TypeError ? 'Cannot reach the simulation API. Start the backend server; see the README run instructions.' : cause instanceof Error ? cause.message : 'Run control failed');
    }
  }

  const units = snapshot?.units ?? [];
  const incidents = snapshot?.incidents ?? [];
  const responseSeries = Object.entries(snapshot?.metrics.response_by_type ?? {}).map(([type, response_s]) => ({ type, response_s }));
  const utilization = Object.entries(snapshot?.metrics.utilization ?? {}).map(([kind, value]) => ({ kind, utilization: value * 100 }));
  const clock = snapshot?.sim_time ?? 0;

  return <main>
    <header>
      <h1>{mode === 'pune' ? 'Pune Emergency Response Simulation' : 'Emergency Response Simulation'}</h1>
      <div className="clock">{Math.floor(clock / 60).toString().padStart(2, '0')}:{Math.floor(clock % 60).toString().padStart(2, '0')}</div>
    </header>
    <nav>
      <label>Seed <input type="number" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label>
      <label>Incidents/min <input type="number" step=".1" value={rate} onChange={event => setRate(Number(event.target.value))} /></label>
      <label>Speed <select value={speed} onChange={event => setSpeed(Number(event.target.value))}>{speedOptions.map(value => <option key={value} value={value}>{value}×</option>)}</select></label>
      <label className="strategy">Strategy <select value={strategies.includes(strategy) ? strategy : strategies[0] ?? 'nearest'} disabled={busy} onChange={event => setStrategy(event.target.value)}>{strategies.map(value => <option key={value} value={value}>{value === 'hungarian' ? 'Hungarian (optimal)' : 'Nearest resource'}</option>)}</select></label>
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
        <h2>{mode === 'pune' ? 'Pune live map' : 'Live City Map'}</h2>
        {mode === 'pune'
          ? puneNetwork ? <PuneMap network={puneNetwork} facilities={facilities} snapshot={snapshot} /> : <p className="map-empty">Loading Pune roads and facilities…</p>
          : <Suspense fallback={<p className="map-empty">Loading developer map…</p>}><GridMap snapshot={snapshot} baseNetwork={baseNetwork} /></Suspense>}
        {mode === 'pune' && <><div className="map-legend"><span><i className="legend-square hospital-legend" />Hospital</span><span><i className="legend-square fire-legend" />Fire station</span><span><i className="legend-square police-legend" />Police station</span><span><i className="legend-diamond" />Incident</span><span><i className="legend-dot" />Response unit</span></div><small className="map-attribution">© OpenStreetMap contributors © CARTO</small></>}
      </article>
      <aside>
        <article><h2>Response Agents</h2>{['ambulance', 'fire', 'police'].map(kind => <div className="agent-card" key={kind}><div className="resource"><span>{kind}</span><b>{snapshot?.agents[kind]?.idle ?? units.filter(unit => unit.kind === kind && unit.status === 'idle').length} idle</b><small>{snapshot?.agents[kind]?.busy ?? units.filter(unit => unit.kind === kind && unit.status !== 'idle').length} busy</small></div><p>{snapshot?.agents[kind]?.last_action ?? 'Standing by'}</p></div>)}<div className="agent-card"><div className="resource"><span>hospital</span><b>{snapshot?.agents.hospital?.beds_free ?? 65} beds</b><small>{snapshot?.agents.hospital?.icu_free ?? 15} ICU</small></div><p>{snapshot?.agents.hospital?.last_action ?? 'Standing by'}</p></div></article>
        <article><h2>Active Incidents</h2>{incidents.filter(incident => incident.status !== 'resolved').slice(-8).map(incident => <div className="resource" key={incident.id}><span>{incident.id} · {incident.type}</span><b className={`sev s${incident.severity}`}>SEV {incident.severity}</b><small>{incident.status}</small></div>)}</article>
        <article>
          <h2>Recent Decisions</h2>
          {decisions.slice(0, 5).map((decision, index) => <button className="decision" key={`${decision.incident_id}-${index}`} onClick={() => setSelected(decision)}>{decision.explanation}</button>)}
          {selected && <div className="candidate-detail"><p>{selected.incident_id} · {selected.unit_id} · ETA {(selected.eta_s / 60).toFixed(1)} min</p><table><thead><tr><th>Unit</th><th>ETA</th><th>Distance</th></tr></thead><tbody>{(selected.candidates ?? []).map(candidate => <tr key={candidate.unit_id}><td>{candidate.unit_id}{candidate.unit_id === selected.unit_id ? ' ✓' : ''}</td><td>{(candidate.eta_s / 60).toFixed(1)} min</td><td>{candidate.distance_m.toFixed(0)} m</td></tr>)}</tbody></table></div>}
        </article>
        <article><h2>Average Response by Type</h2><ResponsiveContainer width="100%" height={150}><LineChart data={responseSeries}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="type" stroke="var(--text-muted)" /><YAxis stroke="var(--text-muted)" /><Tooltip /><Line dataKey="response_s" stroke="var(--accent)" /></LineChart></ResponsiveContainer></article>
        <article><h2>Resource Utilisation</h2><ResponsiveContainer width="100%" height={150}><BarChart data={utilization}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="kind" stroke="var(--text-muted)" /><YAxis stroke="var(--text-muted)" /><Tooltip /><Bar dataKey="utilization" fill="var(--accent)" /></BarChart></ResponsiveContainer></article>
        <article><h2>Latest Strategy Comparison</h2>{comparison ? <table className="comparison"><thead><tr><th>Strategy</th><th>Response</th><th>Utilisation</th><th>Traffic delay</th><th>Improvement</th></tr></thead><tbody>{(['nearest', 'hungarian'] as const).map(name => <tr key={name}><td>{name}</td><td>{comparison.strategies[name]?.avg_response_s?.toFixed(1) ?? '—'} s</td><td>{(((comparison.strategies[name]?.ambulance_util ?? 0) + (comparison.strategies[name]?.fire_util ?? 0) + (comparison.strategies[name]?.police_util ?? 0)) / 3 * 100).toFixed(1)}%</td><td>{comparison.strategies[name]?.mean_traffic_delay_s?.toFixed(1) ?? '—'} s</td><td>{name === 'hungarian' ? `${comparison.improvement_pct.toFixed(1)}%` : '—'}</td></tr>)}</tbody></table> : <p className="empty">No comparison run yet. Run `python -m experiments.run_experiment --compare --scenarios 5` to create one.</p>}</article>
      </aside>
    </section>
  </main>;
}
