import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowUpRight, ArrowRight, Check, Flag, LayoutDashboard, LogOut, Plus, Search, ShieldCheck, Trophy, Users, X, CalendarDays, LockKeyhole} from 'lucide-react';
import {api, type User, type Tournament, type Summary} from './api';
import CreateTournament from './CreateTournament';
import MusicControl from './MusicControl';
import TournamentView from './TournamentView';
import ClubView from './ClubView';
import CompetitionArea from './CompetitionArea';
import {readTournamentRoute,tournamentPath} from './routes';
import './style.css';
import './theme.css';

type Config = {demo: boolean; writes_enabled: boolean};
const finalMusic='https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/'+encodeURIComponent('⚽️ UEFA Champions League 🏆 [TESTO originale + traduzione HQ] - NEW VERSION.mp3');
const swissMusic='https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/Appenzeller%20Jodler.mp3';
const message = (error: unknown) => error instanceof Error ? error.message : 'Operazione non riuscita.';
type Page='home'|'italiana'|'club'|'finali'|'svizzero';
const pageFromLocation=(): Page=>{const path=window.location.pathname;const direct=readTournamentRoute(window.location);if(direct&&(direct.type==='finali'||direct.type==='svizzero'))return direct.type;return path==='/club'?'club':path==='/italiana'?'italiana':path==='/finali'?'finali':path==='/svizzero'?'svizzero':'home';};

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [config, setConfig] = useState<Config>({demo: false, writes_enabled: false});
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState<Tournament | null>(null);
  const [list, setList] = useState<Summary[]>([]);
  const [page, setPage] = useState<Page>(pageFromLocation);
  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [dirty, setDirty] = useState(false);
  const [directRoute,setDirectRoute]=useState(()=>readTournamentRoute(window.location));
  const [competitionName,setCompetitionName]=useState(()=>{const route=readTournamentRoute(window.location);return route&&route.type!=='italiana'?route.name:'';});
  const canWrite = !!user && ['A', 'W'].includes(user.role) && user.password_verified && config.writes_enabled;
  useEffect(() => { Promise.all([api<Config>('/config').then(setConfig), api<User>('/auth/me').then(setUser).catch(() => null)]).catch(e => setError(message(e))).finally(() => setReady(true)); }, []);
  const refresh = () => api<Summary[]>('/tournaments').then(setList).catch(e => setError(message(e)));
  useEffect(() => { if (user) void refresh(); }, [user]);
  useEffect(()=>{const onPop=()=>{setActive(null);setDirty(false);setPage(pageFromLocation());const route=readTournamentRoute(window.location);setDirectRoute(route);setCompetitionName(route&&route.type!=='italiana'?route.name:'');};window.addEventListener('popstate',onPop);return()=>window.removeEventListener('popstate',onPop);},[]);
  useEffect(()=>{
    if(!user||!directRoute)return;
    if(directRoute.type!=='italiana'){
      if(directRoute.type==='finali'||directRoute.type==='svizzero'){setPage(directRoute.type);setCompetitionName(directRoute.name);setDirectRoute(null);return;}
      setPage('home');setError('Tipo di torneo non riconosciuto.');setDirectRoute(null);return;
    }
    let cancelled=false;
    setBusy(true);setError('');
    api<Summary[]>('/tournaments').then(async tournaments=>{
      if(cancelled)return;
      const matches=tournaments.filter(item=>item.name===directRoute.name);
      if(matches.length!==1)throw new Error(matches.length?'Esistono più tornei con questo nome. Aprilo dall’archivio.':'Torneo non trovato. Controlla il nome nel link.');
      const tournament=await api<Tournament>('/tournaments/'+matches[0].id);
      if(cancelled)return;
      setActive(tournament);setPage('italiana');setList(tournaments);
      window.history.replaceState({},'',tournamentPath(tournament.name));
      setDirectRoute(null);
    }).catch(e=>{if(!cancelled){setError(message(e));setPage('italiana');setDirectRoute(null);}}).finally(()=>{if(!cancelled)setBusy(false);});
    return()=>{cancelled=true;};
  },[user?.id,directRoute]);
  const leave = () => !dirty || window.confirm('Ci sono modifiche non salvate. Restano su questo dispositivo. Vuoi cambiare pagina?');
  async function open(id: string) {
    if (!leave()) return;
    setBusy(true); setError(''); setNotice('');
    try { const tournament=await api<Tournament>('/tournaments/' + id);setActive(tournament); setPage('italiana'); setDirty(false); window.history.pushState({},'',tournamentPath(tournament.name)); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }
  async function external(destination: string, tournamentName?: string) {
    if (!leave()) return;
    setBusy(true); setError('');
    try { const result = await api<{url: string}>('/auth/open/' + destination, 'POST'); const url=new URL(result.url); if(tournamentName)url.searchParams.set('torneo',tournamentName); window.location.assign(url.toString()); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }
  async function logout() {
    if (!leave()) return;
    setBusy(true);
    try { await api('/auth/logout', 'POST'); setActive(null); setUser(null); setDirty(false); setError(''); setNotice('');window.history.replaceState({},'','/'); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }
  if (!ready) return <div className="loading"><img className="brand-logo" src="/logo-superba.jpg" alt="Logo Superba"/><p>Benvenuto in Superba…</p></div>;
  if (!user) return <Login config={config} onLogin={setUser} initialError={error}/>;
  const navigate = (next: Page) => { if (leave()) {setPage(next); setActive(null); setDirectRoute(null); setCompetitionName(''); setDirty(false); setNotice(''); setError('');window.history.pushState({},'',next==='home'?'/':`/${next}`);} };
  return <div className="shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => navigate('home')}><img className="brand-logo" src="/logo-superba.jpg" alt="Logo Superba"/><span>SUPERBA<small>SUBBUTEO CLUB</small></span></button>
      <div className="nav-label">IL TUO MONDO</div>
      <nav>
        <button className={page === 'home' ? 'selected' : ''} onClick={() => navigate('home')}><LayoutDashboard size={19}/>Panoramica</button>
        <button className={page === 'club' ? 'selected' : ''} onClick={() => navigate('club')}><Users size={19}/>Gestione club</button>
        <button className={page === 'italiana' ? 'selected' : ''} onClick={() => navigate('italiana')}><Trophy size={19}/>Torneo all’italiana<span className="nav-dot"/></button>
        <button className={page === 'finali' ? 'selected' : ''} onClick={() => navigate('finali')}><Flag size={19}/>Fasi finali</button>
        <button className={page === 'svizzero' ? 'selected' : ''} onClick={() => navigate('svizzero')}><span className="swiss">✚</span>Torneo svizzero</button>
      </nav>
      <div className="sidebar-note"><ShieldCheck size={21}/><strong>Un club. Un solo accesso.</strong><p>Le tue competizioni, tutte da qui.</p></div>
      <div className="profile"><span className="avatar">{user.username.slice(0,1)}</span><span><strong>{user.username}</strong><small>{canWrite ? 'Gestione tornei' : 'Sola lettura'}</small></span><button title="Esci dal portale" aria-label="Esci dal portale" disabled={busy} onClick={logout}><LogOut size={18}/></button></div>
    </aside>
    <main>
      <header className="topbar"><span>Il mondo Superba <span className="muted">/</span> <strong>{page === 'home' ? 'Panoramica' : page === 'club' ? 'Gestione club' : page==='finali'?'Fasi finali':page==='svizzero'?'Svizzero':'All’italiana'}</strong></span><div className="topbar-controls"><MusicControl src={page==='club'?'https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/Gli%20Amici%20(Remastered%202007).mp3':page==='finali'?finalMusic:page==='svizzero'?swissMusic:'/TraLeDita.mp3'}/><span className="environment"><i/>{config.demo ? 'Ambiente dimostrativo' : 'Portale Superba'}</span></div><button className="mobile-logout" aria-label="Esci dal portale" disabled={busy} onClick={logout}><LogOut size={16}/></button></header>
      <div className="content">
        {config.demo && <div className="demo-strip">Stai provando dati dimostrativi. Nessun torneo reale viene modificato.</div>}
        {!config.demo && !config.writes_enabled && <div className="demo-strip">Ambiente in sola lettura: i salvataggi non sono ancora abilitati.</div>}
        {error && <div role="alert" className="alert error">{error}<button aria-label="Chiudi messaggio" onClick={() => setError('')}><X size={16}/></button></div>}
        {notice && <div role="status" className="alert success">{notice}</div>}
        {page==='club' ? <ClubView user={user} canWrite={canWrite} onDirty={setDirty} onLegacy={()=>external('club')}/> : (page==='finali'||page==='svizzero')?<CompetitionArea key={page} kind={page} user={user} canWrite={canWrite} directName={competitionName} onDirty={setDirty} onLegacy={()=>external(page)}/> : active ? <TournamentView key={active.id + ':' + user.id} tournament={active} user={user} canWrite={canWrite} onBack={() => navigate('italiana')} onSaved={value => {setActive(value);window.history.replaceState({},'',tournamentPath(value.name));void refresh();}} onDirty={setDirty} onLegacy={() => external('italiana-classica')} onFinali={() => navigate('finali')}/> : <>
          <section className="page-heading"><div><div className="eyebrow">SUPERBA CLUB · AREA TORNEI</div><h1>{page === 'home' ? `Bentornato, ${user.username}.` : 'Torneo all’italiana'}</h1><p>{page === 'home' ? 'Il prossimo incontro comincia da qui.' : 'Calendari, risultati e classifiche. Tutto sotto controllo.'}</p></div>{canWrite && <button className="primary" onClick={() => setCreating(true)}><Plus size={18}/>Nuovo torneo</button>}</section>
          {page === 'home' && <>
            <section className="hero"><div><span className="hero-kicker"><span className="live-dot"/> IL GIOCO, AL CENTRO</span><h2>La passione è la stessa.<br/>Il campo è tutto nuovo.</h2><p>Organizza il campionato, segui le giornate<br className="desktop"/> e vivi ogni risultato insieme al tuo club.</p><button onClick={() => navigate('italiana')}>Vai ai tornei all’italiana<ArrowRight size={18}/></button></div><div className="pitch" aria-hidden="true"><div className="pitch-line"/><div className="center-circle"/><div className="box top"/><div className="box bottom"/><div className="player p1"/><div className="player p2"/><div className="player p3"/><div className="ball"/></div><span className="hero-number">01 / SUPERBA</span></section>
            <div className="stats"><Stat label="Tornei in archivio" value={list.length} icon={<Trophy/>}/><Stat label="Partite giocate" value={list.reduce((n,t) => n+t.played,0)} icon={<Check/>}/><Stat label="Tornei da completare" value={list.filter(t=>t.played<t.matches).length} icon={<CalendarDays/>}/></div>
          </>}
          <section className="archive"><div className="section-heading"><div><h2>{page === 'home' ? 'I tuoi tornei' : 'Archivio tornei'}</h2><p>Riprendi il gioco da dove lo hai lasciato.</p></div><label className="search"><Search size={17}/><input aria-label="Cerca torneo" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Cerca un torneo…"/></label></div>
            <div className="tournament-list">{list.filter(t=>t.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(t=><button disabled={busy} className="tournament-row" key={t.id} onClick={()=>open(t.id)}><span className="tournament-icon"><Trophy size={22}/></span><span className="tournament-title"><strong>{t.name}</strong><small>{t.groups > 1 && <>{`${t.groups} gironi`}<span>·</span></>}{t.matches} partite</small></span><span className={'badge ' + (t.played === t.matches ? 'done' : '')}>{t.played === t.matches ? 'Completato' : 'In corso'}</span><span className="progress"><span>{t.played}/{t.matches} giocate</span><span className="track"><i style={{width:`${t.played/t.matches*100}%`}}/></span></span><ArrowRight size={18}/></button>)}
              {!list.length && <div className="empty"><Trophy/><h3>Il prossimo torneo ti aspetta</h3><p>{canWrite ? 'Crea il calendario e porta il club in campo.' : 'I tornei disponibili compariranno qui.'}</p></div>}
              {!!list.length && !list.some(t=>t.name.toLowerCase().includes(search.toLowerCase())) && <div className="empty">Nessun torneo corrisponde alla ricerca.</div>}
            </div>
          </section>
          {page === 'home' && <div className="other-worlds"><div><span className="eyebrow">CONTINUA A GIOCARE</span><h2>Le altre competizioni</h2></div><button onClick={()=>navigate('finali')}><Flag/>Fasi finali<ArrowUpRight/></button><button onClick={()=>navigate('svizzero')}><span className="swiss">✚</span>Torneo svizzero<ArrowUpRight/></button></div>}
        </>}
        <footer>SUPERBA SUBBUTEO CLUB<span>La partita continua.</span></footer>
      </div>
    </main>
    {creating && <CreateTournament onClose={()=>setCreating(false)} onCreated={t=>{setActive(t); setPage('italiana'); setCreating(false);window.history.pushState({},'',tournamentPath(t.name));void refresh();}}/>}
  </div>;
}

function Stat({label, value, icon}: {label: string; value: number; icon: React.ReactNode}) {return <div className="stat"><span>{label}<strong>{value.toString().padStart(2,'0')}</strong></span><span className="stat-icon">{icon}</span></div>}

function Login({config,onLogin,initialError}: {config:Config;onLogin:(u:User)=>void;initialError:string}) {
  const [username,setUsername]=useState(''); const [password,setPassword]=useState(''); const [system,setSystem]=useState(''); const [repeat,setRepeat]=useState('');
  const [remember,setRemember]=useState(false); const [activation,setActivation]=useState(false); const [error,setError]=useState(initialError); const [busy,setBusy]=useState(false);
  const [activationUsers,setActivationUsers]=useState<string[]>([]);
  const [userQuery,setUserQuery]=useState('');
  const [loginSuggestions,setLoginSuggestions]=useState<string[]>([]);
  const [lookupBusy,setLookupBusy]=useState(false);
  const filteredUsers=activationUsers.filter(name=>name.toLocaleLowerCase('it').includes(userQuery.toLocaleLowerCase('it')));
  useEffect(()=>{
    const query=username.trim();
    if(activation||query.length<2){setLoginSuggestions([]);return;}
    let cancelled=false;
    const timer=window.setTimeout(()=>{void api<string[]>('/auth/user-suggestions?q='+encodeURIComponent(query)).then(names=>{if(!cancelled)setLoginSuggestions(names);}).catch(()=>{if(!cancelled)setLoginSuggestions([]);});},250);
    return()=>{cancelled=true;window.clearTimeout(timer);};
  },[activation,username]);
  async function loadActivationUsers(){
    setLookupBusy(true);setError('');setUsername('');setActivationUsers([]);
    try{setActivationUsers(await api<string[]>('/auth/activation-users','POST',{system_password:system}));}
    catch(e){setError(message(e));}
    finally{setLookupBusy(false);}
  }
  async function submit(e:React.FormEvent) {e.preventDefault(); setBusy(true); setError(''); try {
    if(activation && !activationUsers.includes(username)) throw new Error('Seleziona un utente del club.');
    if(activation && password!==repeat) throw new Error('Le password non coincidono.');
    onLogin(await api<User>(activation?'/auth/activate':'/auth/login','POST',activation?{username,password,system_password:system}:{username,password,remember}));
  } catch(e) {setError(message(e));} finally {setBusy(false);}}
  return <div className="login-page"><section className="login-story"><div className="brand"><img className="brand-logo" src="/logo-superba.jpg" alt="Logo Superba"/><span>SUPERBA<small>SUBBUTEO CLUB</small></span></div><div><span className="eyebrow">BENVENUTO NEL TUO CLUB</span><h1>Un piccolo campo.<br/>Una grande passione.</h1><p>Un solo accesso per i tuoi tornei,<br/>le classifiche e tutto il mondo Superba.</p></div><small>IL GIOCO CI UNISCE, UNA PARTITA ALLA VOLTA.</small></section><section className="login-panel"><div className="login-form"><span className="login-symbol"><LockKeyhole/></span><h2>{activation?'Il tuo primo accesso':'Entra in Superba'}</h2><p>{activation?'Attiva l’utente già registrato dal gestore.':'Usa il tuo nome giocatore e la password abituale.'}</p>{config.demo&&<div className="demo-strip">Demo: <strong>Andrea</strong> · password <strong>superba-demo</strong></div>}{error&&<div role="alert" className="alert error">{error}</div>}<form onSubmit={submit}>{activation?<><label>Password di sistema<input type="password" required value={system} onChange={e=>{setSystem(e.target.value);setActivationUsers([]);setUsername('');}}/></label><button type="button" className="secondary full" disabled={!system||lookupBusy||busy} onClick={()=>void loadActivationUsers()}>{lookupBusy?'Caricamento…':'Carica utenti del club'}</button>{activationUsers.length>0&&<><label>Cerca utente<input type="search" value={userQuery} onChange={e=>setUserQuery(e.target.value)} placeholder="Cerca il tuo nome…"/></label><label>Nome giocatore<select required value={username} onChange={e=>setUsername(e.target.value)}><option value="">Seleziona il tuo nome</option>{filteredUsers.map(name=><option key={name} value={name}>{name}</option>)}</select></label></>}{!lookupBusy&&activationUsers.length===0&&<small>Inserisci la password di sistema per vedere gli account attivabili.</small>}</>:<label>Nome giocatore<input required autoComplete="username" list="superba-login-users" value={username} onChange={e=>setUsername(e.target.value)} placeholder="Digita almeno 2 lettere…"/><datalist id="superba-login-users">{loginSuggestions.map(name=><option key={name} value={name}/>)}</datalist></label>}<label>Password<input type="password" autoComplete={activation?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)} placeholder="La tua password" required={activation} minLength={activation?10:undefined}/></label>{activation?<label>Conferma password<input type="password" required value={repeat} onChange={e=>setRepeat(e.target.value)}/></label>:<label className="checkbox"><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/>Ricordami su questo dispositivo</label>}<button className="primary full" disabled={busy}>{busy?'Accesso in corso…':activation?'Attiva e accedi':'Accedi al club'}<ArrowRight size={18}/></button></form><button className="text-button full" disabled={busy} onClick={()=>{setActivation(!activation);setError('');}}>{activation?'Torna al login':'Primo accesso? Attiva il tuo account'}</button><div className="separator">oppure</div><button className="secondary full" disabled={busy} onClick={async()=>{setBusy(true);try{onLogin(await api<User>('/auth/guest','POST'));}catch(e){setError(message(e));}finally{setBusy(false);}}}>Esplora come ospite<ArrowUpRight size={17}/></button><p className="login-footnote">I profili lettore possono accedere con il solo nome. Gli ospiti possono consultare i tornei.</p></div></section></div>;
}

createRoot(document.getElementById('root')!).render(<App/>);
