import { useEffect, useState } from 'react';
import Map, { Marker, Source, Layer } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useRunSocket } from './hooks/useRunSocket';

export default function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const [seed, setSeed] = useState(1);
  const [rate, setRate] = useState(0.67);
  const [busy, setBusy] = useState(false);
  const { snapshot, decisions } = useRunSocket(runId);
  useEffect(() => { setBusy(Boolean(snapshot && snapshot.sim_time < 3600)); }, [snapshot]);
  async function start() {
    const response = await fetch('http://localhost:8000/runs', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seed,incident_rate:rate,duration_s:3600})});
    const data = await response.json() as {id:string}; setRunId(data.id); setBusy(true);
  }
  async function control(action: string) { if (runId) await fetch(`http://localhost:8000/runs/${runId}/${action}`, {method:'POST'}); }
  const units = snapshot?.units ?? [];
  const incidents = snapshot?.incidents ?? [];
  const line = incidents.filter(i => i.status === 'resolved').map(i => ({incident:i.id,severity:i.severity}));
  return <main>
    <header><div><small>URBAN RESPONSE NETWORK / PUNE</small><h1>Emergency Operations</h1></div><div className="clock">SIM {Math.floor((snapshot?.sim_time ?? 0)/60).toString().padStart(2,'0')}:{Math.floor((snapshot?.sim_time ?? 0)%60).toString().padStart(2,'0')}</div></header>
    <nav><label>Seed <input type="number" value={seed} onChange={e=>setSeed(Number(e.target.value))}/></label><label>Incidents/min <input type="number" step=".1" value={rate} onChange={e=>setRate(Number(e.target.value))}/></label><button onClick={()=>void start()}>Start</button><button disabled={!runId} onClick={()=>void control('pause')}>Pause</button><button disabled={!runId} onClick={()=>void control('resume')}>Resume</button><button disabled={!runId} onClick={()=>void control('stop')}>Stop</button><span className="live">● {busy ? 'LIVE' : 'STANDBY'}</span></nav>
    <section className="kpis"><article><small>AVG RESPONSE</small><b>{((snapshot?.metrics.avg_response_s ?? 0)/60).toFixed(1)} min</b></article><article><small>ACTIVE INCIDENTS</small><b>{incidents.filter(i=>i.status!=='resolved').length}</b></article><article><small>QUEUED</small><b>{snapshot?.metrics.queued ?? 0}</b></article><article><small>TRAFFIC DELAY</small><b>{(snapshot?.metrics.traffic_delay_s ?? 0).toFixed(1)} s</b></article></section>
    <section className="grid"><article className="map"><h2>Live City Map</h2><Map initialViewState={{longitude:73.86,latitude:18.53,zoom:12}} mapStyle="https://demotiles.maplibre.org/style.json"><Source id="roads" type="geojson" data={{type:'FeatureCollection',features:(snapshot?.traffic??[]).map(e=>({type:'Feature' as const,properties:{congestion:e.congestion},geometry:{type:'LineString' as const,coordinates:e.geometry.map(p=>[p.lon,p.lat])}}))}}><Layer id="traffic" type="line" paint={{'line-color':['interpolate',['linear'],['get','congestion'],0.35,'#27d7a1',1,'#ff4d68'],'line-width':4,'line-opacity':.65}}/></Source>{units.map(u=><Marker key={u.id} longitude={u.location.lon} latitude={u.location.lat}><span className={`unit ${u.kind}`}>{u.kind==='ambulance'?'✚':u.kind==='fire'?'▲':'●'}</span></Marker>)}{incidents.filter(i=>i.status!=='resolved').map(i=><Marker key={i.id} longitude={i.location.lon} latitude={i.location.lat}><span className="incident">{i.severity}</span></Marker>)}</Map></article>
      <aside><article><h2>Response Units</h2>{['ambulance','fire','police'].map(kind=><div className="resource" key={kind}><span>{kind}</span><b>{units.filter(u=>u.kind===kind&&u.status==='idle').length} idle</b><small>{units.filter(u=>u.kind===kind&&u.status!=='idle').length} busy</small></div>)}</article><article><h2>Active Incidents</h2>{incidents.filter(i=>i.status!=='resolved').slice(-8).map(i=><div className="resource" key={i.id}><span>{i.id} · {i.type}</span><b className={`sev s${i.severity}`}>SEV {i.severity}</b><small>{i.status}</small></div>)}</article><article><h2>Recent Decisions</h2>{decisions.slice(0,5).map((d,index)=><p className="decision" key={index}>{d.explanation}</p>)}</article><article><h2>Resolved Incidents</h2><ResponsiveContainer width="100%" height={140}><BarChart data={line}><CartesianGrid strokeDasharray="3 3" stroke="#26334a"/><XAxis dataKey="incident" stroke="#8594ae"/><YAxis stroke="#8594ae"/><Tooltip/><Bar dataKey="severity" fill="#44d6a3"/></BarChart></ResponsiveContainer></article></aside></section>
  </main>;
}
