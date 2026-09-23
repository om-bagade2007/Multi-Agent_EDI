import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import GridMap from './GridMap';
import { assertNoGridTiles } from './lib/mapMode';
import { useRunSocket } from './hooks/useRunSocket';
import type { Comparison, Decision } from './types';

assertNoGridTiles(import.meta.env.VITE_SIMULATION_MODE ?? 'gridsim', []);

export default function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const [seed, setSeed] = useState(1);
  const [rate, setRate] = useState(0.67);
  const [speed, setSpeed] = useState(1);
  const [strategy, setStrategy] = useState('nearest');
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Decision | null>(null);
  const { snapshot, decisions } = useRunSocket(runId);

  useEffect(() => {
    if (snapshot && snapshot.sim_time >= 3600) setBusy(false);
  }, [snapshot]);

  useEffect(() => {
    const refresh = () => { void fetch('http://localhost:8000/experiments/latest').then(response => response.ok ? response.json() : null).then(data => setComparison(data as Comparison | null)).catch(() => setComparison(null)); };
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => { void fetch('http://localhost:8000/scenario').then(response => response.ok ? response.json() : null).then(data => { if (data?.dispatch_strategy) setStrategy(data.dispatch_strategy as string); }).catch(() => undefined); }, []);

  async function start() {
    try {
      setError(null);
      const response = await fetch('http://localhost:8000/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed, incident_rate: rate, duration_s: 3600, speed, strategy }),
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
      <h1>Emergency Response Simulation</h1>
      <div className="clock">{Math.floor(clock / 60).toString().padStart(2, '0')}:{Math.floor(clock % 60).toString().padStart(2, '0')}</div>
    </header>
    <nav>
      <label>Seed <input type="number" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label>
      <label>Incidents/min <input type="number" step=".1" value={rate} onChange={event => setRate(Number(event.target.value))} /></label>
      <label>Speed <select value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={1}>1×</option><option value={5}>5×</option><option value={20}>20×</option></select></label>
      <label className="strategy">Strategy <select value={strategy} disabled={busy} onChange={event => setStrategy(event.target.value)}><option value="nearest">Nearest resource</option><option value="hungarian">Hungarian (optimal)</option></select></label>
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
        <GridMap snapshot={snapshot} />
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
