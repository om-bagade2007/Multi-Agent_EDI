import type { Message, State } from '../types';
export const initialState: State = { snapshot: null, decisions: [], error: null };
export function applyMessage(state: State, message: Message): State {
  if (message.type === 'snapshot') return { ...state, snapshot: message };
  return { ...state, decisions: [message, ...state.decisions].slice(0, 100) };
}
