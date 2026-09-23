export type Coord = { lat: number; lon: number };
export type Unit = { id: string; kind: string; location: Coord; status: string; assigned_incident_id: string | null };
export type Incident = { id: string; type: string; severity: number; location: Coord; created_at: number; status: string };
export type Decision = { type: 'decision'; incident_id: string; unit_id: string; eta_s: number; explanation: string; candidates?: { unit_id: string; eta_s: number; distance_m: number }[] };
export type Snapshot = {
  type: 'snapshot'; sim_time: number; units: Unit[]; incidents: Incident[];
  stations: { id: string; kind: string; location: Coord }[];
  agents: Record<string, { idle?: number; busy?: number; beds_free?: number; icu_free?: number; last_action: string }>;
  hospitals: { id: string; location: Coord; beds_free: number; icu_free: number }[];
  traffic: { id: string; geometry: Coord[]; congestion: number }[];
  metrics: { avg_response_s: number; traffic_delay_s: number; queued: number; response_by_type: Record<string, number>; utilization: Record<string, number> };
};
export type Message = Snapshot | Decision;
export type State = { snapshot: Snapshot | null; decisions: Decision[]; error: string | null };
