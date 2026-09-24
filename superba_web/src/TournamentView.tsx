import {useEffect, useRef, useState, type CSSProperties} from 'react';
import {ArrowLeft, ArrowRight, ArrowUpRight, ChevronDown, Copy, Download, RefreshCw, Save, ShieldCheck, Trophy} from 'lucide-react';
import {api, type Match, type Tournament, type User} from './api';
import {tournamentPath} from './routes';
import {BadgeEditor, TeamMark, type BadgeMap} from './TeamBadges';

type Draft = {home:number;away:number;valid:boolean};
type Drafts = Record<number,Draft>;
type NameMode = 'complete'|'teams'|'players';
type Status = 'all'|'played'|'unplayed';
type Leg = 'both'|'first'|'return';
type ViewMode = 'compact'|'premium'|'standard';

function shownName(value:string,mode:NameMode){
  if(mode==='complete')return value;
  const separator=value.includes(' - ')?' - ':'-';
  const index=value.indexOf(separator);
  if(index<0)return value;
  return mode==='teams'?value.slice(0,index).trim():value.slice(index+separator.length).trim();
}

function isReturnLeg(groupRows:Match[]){
  const pairs=new Set(groupRows.map(r=>`${r.home}\u0000${r.away}`));
  return groupRows.some(r=>pairs.has(`${r.away}\u0000${r.home}`));
}

export default function TournamentView({tournament:t,user,canWrite,onBack,onSaved,onDirty,onLegacy,onFinali,routeType='italiana'}:{tournament:Tournament;user:User;canWrite:boolean;onBack:()=>void;onSaved:(t:Tournament)=>void;onDirty:(b:boolean)=>void;onLegacy:()=>void;onFinali:()=>void;routeType?:string}){
  const draftKey=`superba-drafts:${user.id}:${t.id}`;
  const preferenceKey=`superba-view:${user.id}`;
  const [drafts,setDrafts]=useState<Drafts>(()=>{try{return JSON.parse(localStorage.getItem(draftKey)||'{}').drafts||{};}catch{return {};}});
  const [draftVersion,setDraftVersion]=useState(()=>{try{return JSON.parse(localStorage.getItem(draftKey)||'{}').version||t.version;}catch{return t.version;}});
  const [group,setGroup]=useState(t.matches[0]?.group||'');
  const [day,setDay]=useState(t.matches.find(r=>!r.valid)?.day||1);
  const [tab,setTab]=useState<'matches'|'standings'|'withdrawals'>('matches');
  const [allMatches,setAllMatches]=useState(false);
  const [status,setStatus]=useState<Status>('all');
  const [leg,setLeg]=useState<Leg>('both');
  const [player,setPlayer]=useState('');
  const [filterGroup,setFilterGroup]=useState('');
  const [filtersOpen,setFiltersOpen]=useState(false);
  const [nameMode,setNameMode]=useState<NameMode>(()=>{try{return JSON.parse(localStorage.getItem(preferenceKey)||'{}').nameMode||'teams';}catch{return 'teams';}});
  const [viewMode,setViewMode]=useState<ViewMode>(()=>{try{const value=JSON.parse(localStorage.getItem(preferenceKey)||'{}').viewMode;return ['compact','premium','standard'].includes(value)?value:'compact';}catch{return 'compact';}});
  const [retiring,setRetiring]=useState<string[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [rename,setRename]=useState(false);
  const [name,setName]=useState(t.name);
  const [celebrating,setCelebrating]=useState(false);
  const [badgeEditorOpen,setBadgeEditorOpen]=useState(false);
  const victoryAudio=useRef<HTMLAudioElement>(null);
  const dirty=Object.keys(drafts).length>0;
  const conflict=dirty&&draftVersion!==t.version;
  const writable=canWrite&&!t.closed&&(!t.name.includes('Campionato')||user.role==='A');
  const groups=[...new Set(t.matches.map(r=>r.group))];
  const participants=[...new Set(t.matches.flatMap(r=>[r.home,r.away]))].sort();
  const days=[...new Set(t.matches.filter(r=>r.group===group).map(r=>r.day))].sort((a,b)=>a-b);
  const selectedDay=days.includes(day)?day:days[0];
  const hasReturn=groups.some(g=>isReturnLeg(t.matches.filter(r=>r.group===g)));
  const played=t.matches.filter(r=>r.valid).length;
  const winners=groups.map(g=>{const winner=t.standings.find(s=>s.Girone===g);return winner?`${groups.length>1?g+': ':''}${winner.Squadra}`:'';}).filter(Boolean).join(' · ');

  useEffect(()=>{onDirty(dirty);try{if(dirty)localStorage.setItem(draftKey,JSON.stringify({drafts,version:draftVersion}));else localStorage.removeItem(draftKey);}catch{setError('Il browser non può conservare le bozze. Salva prima di uscire.');}},[drafts,draftVersion,draftKey]);
  useEffect(()=>{try{localStorage.setItem(preferenceKey,JSON.stringify({nameMode,viewMode}));}catch{}},[nameMode,viewMode,preferenceKey]);
  useEffect(()=>{const handler=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[dirty]);

  function change(row:Match,patch:Partial<Draft>){
    if(!dirty)setDraftVersion(t.version);
    setDrafts(previous=>{const next={...previous};next[row.index]={...(previous[row.index]??{home:row.home_goals,away:row.away_goals,valid:row.valid}),...patch};
      if(next[row.index].home===row.home_goals&&next[row.index].away===row.away_goals&&next[row.index].valid===row.valid)delete next[row.index];return next;});
    setNotice('');
  }
  async function action(path:string,method:string,body:unknown){
    setBusy(true);setError('');setNotice('');
    try{const saved=await api<Tournament>('/tournaments/'+t.id+path,method,body);onSaved(saved);setDrafts({});setDraftVersion(saved.version);
      setNotice(saved.completion_warnings?.length?saved.completion_warnings.join(' '):'Operazione completata e salvata.');setRename(false);setRetiring([]);}
    catch(e){setError(e instanceof Error?e.message:'Operazione non riuscita.');}
    finally{setBusy(false);}
  }
  async function reload(){
    if(dirty&&!window.confirm('Ricaricando elimini le bozze. Puoi prima scaricarle. Continuare?'))return;
    setBusy(true);
    try{const loaded=await api<Tournament>('/tournaments/'+t.id);onSaved(loaded);setDrafts({});setDraftVersion(loaded.version);setError('');setNotice('Torneo aggiornato.');}
    catch(e){setError(e instanceof Error?e.message:'Ricaricamento non riuscito.');}
    finally{setBusy(false);}
  }
  async function saveBadges(badges:BadgeMap){
    setBusy(true);setError('');
    try{const saved=await api<Tournament>(`/tournaments/${t.id}/badges`,'PATCH',{version:t.version,badges});onSaved(saved);setBadgeEditorOpen(false);setNotice('Immagini Premium salvate.');}
    catch(e){setError(e instanceof Error?e.message:'Salvataggio immagini non riuscito.');}
    finally{setBusy(false);}
  }
  function exportDrafts(){const url=URL.createObjectURL(new Blob([JSON.stringify({tournament_id:t.id,version:draftVersion,results:drafts},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='bozze-superba.json';a.click();URL.revokeObjectURL(url);}
  const rows=(allMatches?t.matches:t.matches.filter(r=>r.group===group&&r.day===selectedDay)).filter(row=>{
    if(!allMatches)return true;
    if(filterGroup&&row.group!==filterGroup)return false;
    if(player&&row.home!==player&&row.away!==player)return false;
    if(status==='played'&&!row.valid)return false;
    if(status==='unplayed'&&row.valid)return false;
    if(leg!=='both'){
      const groupRows=t.matches.filter(r=>r.group===row.group);
      const second=isReturnLeg(groupRows)&&row.day>Math.max(...groupRows.map(r=>r.day))/2;
      if(leg==='first'&&second)return false;
      if(leg==='return'&&!second)return false;
    }
    return true;
  }).sort((a,b)=>a.group.localeCompare(b.group)||a.day-b.day||a.index-b.index);

  return <>
    <button className="back" onClick={onBack} disabled={busy}><ArrowLeft size={16}/>Tutti i tornei</button>
    <section className="page-heading tournament-heading arena-hero">
      <div className="arena-copy"><div className="eyebrow"><span className="arena-live-dot"/> SUPERBA MATCH CENTER · {routeType==='finali'?(groups.length>1?'FASI FINALI · GIRONI':'FASI FINALI'):'ALL’ITALIANA'}</div><h1>{routeType==='finali'?'Fase a gironi · '+t.name.replace(/^fasefinaleAGironi_/,''):t.name}</h1><p>Ogni partita conta. Segui il torneo, vivi la giornata.</p><div className="arena-facts"><span><strong>{played}<em>/{t.matches.length}</em></strong>partite validate</span>{groups.length>1&&<span><strong>{groups.length}</strong>gironi</span>}<span><strong>{days.length}</strong>{groups.length>1?'giornate per girone':'giornate'}</span></div></div>
      <div className="arena-visual" aria-hidden="true"><div className="arena-field"><i className="arena-midline"/><i className="arena-circle"/><i className="arena-box arena-box-top"/><i className="arena-box arena-box-bottom"/><i className="arena-disc disc-one"/><i className="arena-disc disc-two"/><i className="arena-disc disc-three"/><i className="arena-ball"/></div><span className="arena-orbit orbit-one"/><span className="arena-orbit orbit-two"/></div>
      <span className={'badge '+(t.complete?'done':'')}>{t.closed?'🏆 Concluso':t.complete?'✨ Da concludere':'● In corso'}</span><div className="arena-progress" style={{width:`${Math.max(2,played/t.matches.length*100)}%`}}/>
    </section>
    {error&&<div className="alert error" role="alert">{error}</div>}{notice&&<div className="alert success" role="status">{notice}</div>}{conflict&&<div className="alert error">Le bozze appartengono a una versione precedente. Scaricale prima di ricaricare e confrontare i risultati.</div>}
    {t.complete&&winners&&<section className="victory-panel"><div><Trophy size={25}/><strong>{celebrating?'🎉 Torneo completato!':'Tutte le partite sono validate'}</strong><span>{winners}</span></div><button type="button" className="victory-button" onClick={()=>{setCelebrating(true);victoryAudio.current?.pause();if(victoryAudio.current)victoryAudio.current.currentTime=0;void victoryAudio.current?.play().catch(()=>{});}}>🏆 Celebra vincitori 🎉</button>{celebrating&&<div className="victory-confetti" aria-hidden="true">🎈 🎊 🏆 🎊 🎈</div>}<audio ref={victoryAudio} src="/wearethechamp.mp3" preload="none"/></section>}
    <div className="tournament-toolbar"><div className="tabs"><button className={tab==='matches'?'active':''} onClick={()=>setTab('matches')}>⚽ Partite</button><button className={tab==='standings'?'active':''} onClick={()=>setTab('standings')}>🏆 Classifica</button><button className={tab==='withdrawals'?'active':''} onClick={()=>setTab('withdrawals')}>🚩 Abbandoni</button></div><div className="toolbar-actions"><button className="secondary compact share-link" onClick={async()=>{const url=new URL(tournamentPath(t.name,routeType),window.location.origin).toString();try{await navigator.clipboard.writeText(url);setNotice('Link diretto copiato. Chi lo apre dovrà accedere al portale.');}catch{window.prompt('Copia il link diretto al torneo',url);}}}><Copy size={16}/>Copia link</button><button disabled={busy} className="icon-button" title="Ricarica torneo" aria-label="Ricarica torneo" onClick={reload}><RefreshCw size={17}/></button><a className="secondary compact" href={`/api/tournaments/${t.id}/export.pdf`}><Download size={16}/>PDF</a><a className="secondary compact" href={`/api/tournaments/${t.id}/export.csv`}>CSV</a></div></div>
    {tab==='matches'&&<>
      <section className={'filter-panel'+(filtersOpen?'':' collapsed')}><div className="filter-head"><button type="button" className="filter-toggle" aria-expanded={filtersOpen} onClick={()=>setFiltersOpen(value=>!value)}>🎯 Filtri e nomi <ChevronDown size={17}/></button><div className="segmented"><button className={!allMatches?'active':''} onClick={()=>setAllMatches(false)}>Per giornata</button><button className={allMatches?'active':''} onClick={()=>{setAllMatches(true);setFiltersOpen(true);}}>Tutte le partite</button></div></div>
        {filtersOpen&&<div className="filter-grid"><label>Formato nomi<select value={nameMode} onChange={e=>setNameMode(e.target.value as NameMode)}><option value="complete">Squadra e giocatore</option><option value="teams">Solo squadre</option><option value="players">Solo giocatori</option></select></label>
        {allMatches?<><label>Stato partite<select value={status} onChange={e=>setStatus(e.target.value as Status)}><option value="all">Tutte</option><option value="played">Giocate</option><option value="unplayed">Da giocare</option></select></label><label>Andata / ritorno<select value={leg} onChange={e=>setLeg(e.target.value as Leg)}><option value="both">Entrambe</option><option value="first">Andata</option><option value="return" disabled={!hasReturn}>Ritorno</option></select></label><label>Giocatore<select value={player} onChange={e=>setPlayer(e.target.value)}><option value="">Tutti i giocatori</option>{participants.map(p=><option key={p} value={p}>{shownName(p,nameMode)}</option>)}</select></label>{groups.length>1&&<label>Girone<select value={filterGroup} onChange={e=>setFilterGroup(e.target.value)}><option value="">Tutti i gironi</option>{groups.map(g=><option key={g}>{g}</option>)}</select></label>}</>:groups.length>1&&<label>Girone<select value={group} onChange={e=>{setGroup(e.target.value);setDay(1);}}>{groups.map(g=><option key={g}>{g}</option>)}</select></label>}</div>}
      </section>
      <div className="view-switcher"><span>Vista incontri</span><div className="segmented" role="group" aria-label="Vista incontri">{(['compact','premium','standard'] as ViewMode[]).map(mode=><button key={mode} className={viewMode===mode?'active':''} aria-pressed={viewMode===mode} onClick={()=>setViewMode(mode)}>{mode==='compact'?'Compact':mode==='premium'?'Premium':'Standard'}</button>)}</div>{viewMode==='premium'&&writable&&<button type="button" className="secondary compact" disabled={dirty||busy} onClick={()=>setBadgeEditorOpen(true)}>🛡️ Bandiere e stemmi</button>}</div>
      {!allMatches&&<div className="round-selector"><div className="round-selector-head"><span>📅 Giornata {selectedDay} <small>di {days.length}</small></span><div><button aria-label="Giornata precedente" disabled={days.indexOf(selectedDay)<=0} onClick={()=>setDay(days[days.indexOf(selectedDay)-1])}><ArrowLeft size={17}/></button><button aria-label="Giornata successiva" disabled={days.indexOf(selectedDay)>=days.length-1} onClick={()=>setDay(days[days.indexOf(selectedDay)+1])}><ArrowRight size={17}/></button></div></div><div className="round-track" aria-label="Seleziona giornata">{days.map(d=><button key={d} className={d===selectedDay?'active':''} aria-current={d===selectedDay?'step':undefined} onClick={()=>setDay(d)}>G{d}</button>)}</div></div>}
      <section className="results-card tournament-results"><div className="results-heading"><h3>{allMatches?`⚽ Partite filtrate (${rows.length})`:`⚽ ${groups.length>1?`${group} · `:''}Giornata ${selectedDay}`}</h3><span>{rows.filter(r=>(drafts[r.index]?.valid??r.valid)).length}/{rows.length} validate</span></div><div className={`matches ${viewMode}`} key={allMatches?'all':`${group}-${selectedDay}`}>{rows.map((row,index)=>{const value=drafts[row.index]||{home:row.home_goals,away:row.away_goals,valid:row.valid};return <div className={'match-row '+(drafts[row.index]?'edited':'')} style={{'--match-order':Math.min(index,12)} as CSSProperties} key={row.index}><span className="match-meta">{allMatches?`${groups.length>1?`${row.group} · `:''}G${row.day}`:`PARTITA ${String(index+1).padStart(2,'0')}`}</span><span className="team home" title={row.home}>{allMatches&&<small className="compact-day">{groups.length>1?`${row.group.replace(/^Girone\s*/,'')}·G${row.day}`:`G${row.day}`}</small>}<span className="team-mark"><TeamMark name={row.home} badge={viewMode==='premium'?t.badges?.[row.home]:undefined}/></span><span>{shownName(row.home,nameMode)}</span></span><div className="score"><input aria-label={`Gol casa ${row.home}`} type="number" min={0} max={20} value={value.home} disabled={!writable||busy} onChange={e=>change(row,{home:Number(e.target.value)})}/><span>:</span><input aria-label={`Gol ospite ${row.away}`} type="number" min={0} max={20} value={value.away} disabled={!writable||busy} onChange={e=>change(row,{away:Number(e.target.value)})}/></div><span className="team away" title={row.away}><span>{shownName(row.away,nameMode)}</span><span className="team-mark alt"><TeamMark name={row.away} badge={viewMode==='premium'?t.badges?.[row.away]:undefined}/></span></span><label className={'validate '+(value.valid?'valid':'')}><input type="checkbox" aria-label={`Valida ${row.home} contro ${row.away}`} checked={value.valid} disabled={!writable||busy} onChange={e=>change(row,{valid:e.target.checked})}/>{value.valid?'✓ Validata':'○ Da validare'}</label></div>})}{!rows.length&&<div className="empty">Nessuna partita corrisponde ai filtri.</div>}<div className="results-note"><ShieldCheck size={16}/>La classifica considera solo risultati salvati e validati. Puoi modificare anche più partite filtrate prima di salvare.</div></div></section>
    </>}
    {tab==='standings'&&<section className="results-card"><div className="results-heading">{groups.length>1?<label className="select-label">Girone<select aria-label="Girone classifica" value={group} onChange={e=>setGroup(e.target.value)}>{groups.map(g=><option key={g}>{g}</option>)}</select></label>:<h3>🏆 Classifica</h3>}</div><div className="table-scroll"><table><thead><tr><th>#</th><th>Squadra / giocatore</th><th>Pt</th><th>G</th><th>V</th><th>P</th><th>S</th><th>GF</th><th>GS</th><th>DR</th></tr></thead><tbody>{t.standings.filter(s=>s.Girone===group).map((s,i)=><tr key={s.Squadra}><td>{i+1}</td><td>{s.Squadra}{s.Ritirato&&<span className="badge">Ritirato</span>}</td><td className="points">{s.Punti}</td><td>{s.G}</td><td>{s.V}</td><td>{s.P}</td><td>{s.S}</td><td>{s.GF}</td><td>{s.GS}</td><td>{s.DR>0?'+':''}{s.DR}</td></tr>)}</tbody></table>{!t.standings.some(s=>s.Girone===group)&&<div className="empty">Valida e salva la prima partita per vedere la classifica.</div>}</div></section>}
    {tab==='withdrawals'&&<section className="results-card withdrawal-panel"><h3>Gestione abbandoni</h3><p>Seleziona uno o più partecipanti. Le partite contro giocatori ancora attivi diventano 0–3; tra due ritirati il risultato è 0–0.</p>{t.withdrawals.length>0&&<p>Già ritirati: {t.withdrawals.map(x=>shownName(x,nameMode)).join(', ')}</p>}<div className="withdrawal-options">{participants.filter(p=>!t.withdrawals.includes(p)).map(p=><label className="checkbox" key={p}><input type="checkbox" disabled={!writable||busy} checked={retiring.includes(p)} onChange={e=>setRetiring(current=>e.target.checked?[...current,p]:current.filter(x=>x!==p))}/>{shownName(p,nameMode)}</label>)}</div>{writable&&<button className="primary" disabled={!retiring.length||dirty||busy} onClick={()=>{if(window.confirm(`Confermi l’abbandono di ${retiring.map(x=>shownName(x,nameMode)).join(', ')}? I risultati interessati saranno aggiornati.`))void action('/withdrawals','POST',{version:t.version,teams:retiring});}}>Conferma abbandono</button>}</section>}
    {dirty&&<div className="savebar"><span><span className="status-dot pending"/>{Object.keys(drafts).length} partite con modifiche non salvate</span><div><button className="text-button" onClick={exportDrafts}>Scarica bozze</button><button className="primary" disabled={!writable||busy||conflict} onClick={()=>action('/results','PATCH',{version:draftVersion,results:Object.entries(drafts).map(([index,value])=>({index:Number(index),...value}))})}><Save size={17}/>{busy?'Salvataggio…':'Salva risultati'}</button></div></div>}
    {writable&&<details className="manage"><summary>Gestisci torneo<ChevronDown size={17}/></summary><div className="manage-content"><button className="secondary" disabled={dirty||busy} onClick={()=>setRename(!rename)}>Rinomina torneo</button>{rename&&<form onSubmit={e=>{e.preventDefault();void action('/name','PATCH',{name,version:t.version});}}><input aria-label="Nuovo nome torneo" required maxLength={160} value={name} onChange={e=>setName(e.target.value)}/><button className="primary" disabled={busy}>Salva nome</button></form>}</div></details>}
    {t.complete&&!t.closed&&writable&&<div className="completion"><Trophy/><div><h3>Tutte le partite sono validate</h3><p>Concludi per archiviare una copia del torneo e aggiornare il palmarès dei vincitori.</p></div><button className="primary" disabled={dirty||busy} onClick={()=>{if(window.confirm('Concludere il torneo e assegnare le vittorie nel palmarès?'))void action('/complete','POST',{version:t.version});}}>Concludi torneo</button></div>}
    {t.closed&&!t.archived&&canWrite&&(!t.name.includes('Campionato')||user.role==='A')&&<button className="text-button" disabled={busy} onClick={()=>action('/complete','POST',{version:t.version})}>Verifica e completa l’aggiornamento del palmarès</button>}
    {t.closed&&routeType!=='finali'&&<button className="secondary finali-button" disabled={busy} onClick={onFinali}>Vai alle fasi finali<ArrowUpRight size={16}/></button>}
    {badgeEditorOpen&&<BadgeEditor participants={participants} badges={t.badges||{}} busy={busy} error={error} onClose={()=>setBadgeEditorOpen(false)} onSave={saveBadges}/>}
    <div className="legacy-note"><span>La versione classica resta disponibile durante la migrazione.</span><button className="text-button" disabled={busy} onClick={onLegacy}>Apri versione classica<ArrowUpRight size={15}/></button></div>
  </>;
}
