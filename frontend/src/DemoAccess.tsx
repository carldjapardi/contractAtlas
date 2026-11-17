import { useEffect, useState } from 'react';
import { api } from './api';

export default function DemoAccess() {
  const [locked, setLocked] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api<{required:boolean;authorized:boolean}>('/access').then(value => setLocked(value.required && !value.authorized)).catch(() => {}); }, []);
  if (!locked) return null;
  return <section className="team-brief-card" aria-label="Live demo access"><h2>Run live research</h2><p>You can inspect the completed demo now. Enter the shared demo code to run new agents.</p><form onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError('');
    try { await api('/access', { method:'POST', body:JSON.stringify({code}) }); setCode(''); setLocked(false); }
    catch (error) { setError(error instanceof Error ? error.message : 'Could not unlock live research.'); }
    finally { setBusy(false); }
  }} style={{display:'flex',gap:12,flexWrap:'wrap',marginTop:12}}><input aria-label="Demo access code" type="password" autoComplete="current-password" value={code} onChange={event=>setCode(event.target.value)} required maxLength={200} /><button className="button-secondary" disabled={busy}>{busy ? 'Unlocking…' : 'Unlock live research'}</button></form>{error && <p role="alert">{error}</p>}</section>;
}
