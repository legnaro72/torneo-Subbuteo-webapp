export type User = {id: string; username: string; role: string; password_verified: boolean};
export type Match = {index: number; group: string; day: number; home: string; away: string; home_goals: number; away_goals: number; valid: boolean};
export type Standing = {Squadra: string; Girone: string; Punti: number; G: number; V: number; P: number; S: number; GF: number; GS: number; DR: number; Ritirato: boolean};
export type Tournament = {id: string; name: string; version: string; matches: Match[]; standings: Standing[]; complete: boolean; closed: boolean; archived: boolean; withdrawals: string[]; badges?: import('./TeamBadges').BadgeMap; completion_warnings?: string[]};
export type Summary = {id: string; name: string; matches: number; played: number; groups: number};
export type Player = {id: string; name: string; team: string; potential: string};
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function api<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  let response: Response;
  try { response = await fetch('/api' + path, {method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-Superba-Request': '1'}, body: data === undefined ? undefined : JSON.stringify(data)}); }
  catch { throw new ApiError(0, 'Connessione assente. Le modifiche non salvate restano su questo dispositivo.'); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, typeof body.detail === 'string' ? body.detail : 'Verifica i dati inseriti e riprova.');
  return body as T;
}
