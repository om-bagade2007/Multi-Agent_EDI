import { describe, expect, it } from 'vitest';
import { applyMessage, initialState } from './reducer';
describe('applyMessage', () => {
  it('applies snapshots and decisions', () => {
    const snap = { type: 'snapshot' as const, sim_time: 10, units: [], incidents: [], stations: [], hospitals: [], agents: {}, traffic: [], metrics: { avg_response_s: 0, traffic_delay_s: 0, queued: 0, response_by_type: {}, utilization: {} } };
    const state = applyMessage(initialState, snap);
    expect(state.snapshot?.sim_time).toBe(10);
    expect(applyMessage(state, {type:'decision',incident_id:'I1',unit_id:'A1',eta_s:10,explanation:'fast'}).decisions).toHaveLength(1);
  });
});
