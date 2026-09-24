import {useEffect, useMemo, useState} from 'react';
import {ArrowUpRight, Download, RefreshCw, Save, Search, ShieldCheck, Trophy, UserPlus, X} from 'lucide-react';
import {api, type User} from './api';

type Role='R'|'W'|'A';
type ClubPlayer={id:string;version:string;name:string;team:string;potential:number;role:Role;password_set:boolean;
  NCampionatiVinti:number;listaCampionatiVinti:string[];NGironiFFVinti:number;listaGironiFFVinti:string[];NFFElimDirettaVinte:number;listaFFElimDirettaVinte:string[]};
type ClubTournament={id:string;scope:'italiana'|'svizzero';name:string;championship:boolean};
type PlayerFields={name:string;team:string;potential:number;role:Role};
type Deletion={targets:ClubTournament[];allExceptChampionships:boolean;clearScope?:'italiana'|'svizzero'|'all'};
const roleName:Record<Role,string>={R:'Reader',W:'Writer',A:'Amministratore'};
const message=(e:unknown)=>e instanceof Error?e.message:'Operazione non riuscita.';

export default function ClubView({user,canWrite,onDirty,onLegacy}:{user:User;canWrite:boolean;onDirty:(value:boolean)=>void;onLegacy:()=>void}){
  const admin=canWrite&&user.role==='A';
  const [players,setPlayers]=useState<ClubPlayer[]>([]);
  const [tournaments,setTournaments]=useState<ClubTournament[]>([]);
  const [tab,setTab]=useState<'players'|'palmares'|'tournaments'>('players');
  const [search,setSearch]=useState('');
  const [drafts,setDrafts]=useState<Record<string,Partial<PlayerFields>>>({});
  const [form,setForm]=useState<(PlayerFields&{id?:string;version?:string})|null>(null);
  const [detail,setDetail]=useState('');
  const [selected,setSelected]=useState<string[]>([]);
  const [deletion,setDeletion]=useState<Deletion|null>(null);
  const [password,setPassword]=useState('');
  const [confirmation,setConfirmation]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const dirty=Object.keys(drafts).length>0||form!==null;
  useEffect(()=>{onDirty(dirty);},[dirty,onDirty]);
  useEffect(()=>{void refresh();},[]);

  async function refresh(){
    setBusy(true);setError('');
    try{const [p,t]=await Promise.all([api<ClubPlayer[]>('/club/players'),api<ClubTournament[]>('/club/tournaments')]);setPlayers(p);setTournaments(t);setDrafts({});}
    catch(e){setError(message(e));}
    finally{setBusy(false);}
  }
  function patch(id:string,change:Partial<PlayerFields>){setDrafts(current=>({...current,[id]:{...current[id],...change}}));}
  function edit(p:ClubPlayer){setForm({id:p.id,version:p.version,name:p.name,team:p.team,potential:p.potential,role:p.role});setError('');}
  function create(){setForm({name:'',team:'',potential:4,role:'R'});setError('');}
  async function savePlayer(){
    if(!form||!form.name.trim()||!Number.isInteger(form.potential)||form.potential<1||form.potential>10)return;
    setBusy(true);setError('');
    try{const payload={name:form.name.trim(),team:form.team.trim(),potential:form.potential,...(admin?{role:form.role}:{})};
      if(form.id)await api('/club/players/'+form.id,'PATCH',{...payload,version:form.version});
      else await api('/club/players','POST',payload);
      setForm(null);setNotice('Giocatore salvato.');await refresh();}
    catch(e){setError(message(e));}
    finally{setBusy(false);}
  }
  async function saveTable(){
    const changed=players.filter(p=>drafts[p.id]);
    if(!changed.length)return;
    setBusy(true);setError('');
    try{await api('/club/players/bulk','POST',{players:changed.map(p=>({id:p.id,version:p.version,name:drafts[p.id].name??p.name,
      team:drafts[p.id].team??p.team,potential:drafts[p.id].potential??p.potential,role:drafts[p.id].role??p.role}))});
      setNotice(`${changed.length} giocatori aggiornati.`);await refresh();}
    catch(e){setError(message(e));}
    finally{setBusy(false);}
  }
  async function deletePlayer(p:ClubPlayer){
    if(!window.confirm(`Eliminare definitivamente ${p.name} dall’anagrafica?`))return;
    setBusy(true);setError('');
    try{await api('/club/players/'+p.id,'DELETE',{version:p.version});setForm(null);setNotice('Giocatore eliminato.');await refresh();}
    catch(e){setError(message(e));}
    finally{setBusy(false);}
  }
  async function resetPassword(p:ClubPlayer){
    if(!window.confirm(`Resettare la password di ${p.name}? Dovrà attivare di nuovo il proprio accesso.`))return;
    setBusy(true);setError('');
    try{await api('/club/players/'+p.id+'/reset-password','POST');setNotice('Password resettata; le sessioni precedenti sono revocate.');await refresh();}
    catch(e){setError(message(e));}
    finally{setBusy(false);}
  }
  const selectionKey=(t:ClubTournament)=>`${t.scope}:${t.id}`;
  function prepareDelete(targets:ClubTournament[],allExceptChampionships=false,clearScope?:'italiana'|'svizzero'|'all'){
    if(!targets.length)return;
    setDeletion({targets,allExceptChampionships,clearScope});setPassword('');setConfirmation('');setError('');
  }
  async function confirmDelete(){
    if(!deletion||confirmation!=='ELIMINA')return;
    setBusy(true);setError('');
    try{const result=await api<{deleted:number}>('/club/tournaments/delete','POST',{
      targets:deletion.targets.map(({id,scope,name})=>({id,scope,name})),all_except_championships:deletion.allExceptChampionships,clear_scope:deletion.clearScope??null,password});
      setNotice(`${result.deleted} tornei eliminati.`);setDeletion(null);setSelected([]);await refresh();}
    catch(e){setError(message(e));}
    finally{setBusy(false);}
  }
  const filteredPlayers=players.filter(p=>`${p.name} ${p.team}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const chosen=players.find(p=>p.id===detail);
  const totalTrophies=(p:ClubPlayer)=>p.NCampionatiVinti+p.NGironiFFVinti+p.NFFElimDirettaVinte;
  const sortedPalmares=useMemo(()=>[...players].sort((a,b)=>totalTrophies(b)-totalTrophies(a)||a.name.localeCompare(b.name)),[players]);
  const needsPassword=!!deletion&&(deletion.allExceptChampionships||deletion.targets.some(t=>t.championship));

  return <>
    <section className="page-heading"><div><span className="eyebrow">SUPERBA CLUB · ANAGRAFICA E ARCHIVIO</span><h1>Gestione club</h1><p>Giocatori, palmarès e tornei del mondo Superba.</p></div><button className="secondary" disabled={busy} onClick={()=>void refresh()}><RefreshCw size={16}/>Aggiorna</button></section>
    {error&&<div className="alert error" role="alert">{error}</div>}{notice&&<div className="alert success" role="status">{notice}</div>}
    {!canWrite&&<div className="demo-strip">Il tuo profilo può consultare il club in sola lettura.</div>}
    <div className="tournament-toolbar"><div className="tabs"><button className={tab==='players'?'active':''} onClick={()=>setTab('players')}>Giocatori</button><button className={tab==='palmares'?'active':''} onClick={()=>setTab('palmares')}>Palmarès</button><button className={tab==='tournaments'?'active':''} onClick={()=>setTab('tournaments')}>Archivio tornei</button></div><div className="toolbar-actions"><a className="secondary compact" href="/api/club/export.csv"><Download size={16}/>CSV</a><a className="secondary compact" href="/api/club/export.pdf"><Download size={16}/>PDF Club</a></div></div>
    {tab==='players'&&<section className="results-card club-section"><div className="section-heading"><div><h2>Rosa giocatori</h2><p>{players.length} tesserati · potenziale medio {players.length?(players.reduce((n,p)=>n+p.potential,0)/players.length).toFixed(1):'0.0'}/10</p></div><div className="club-actions"><label className="search"><Search size={16}/><input aria-label="Cerca giocatore" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Cerca giocatore…"/></label>{canWrite&&<button className="primary" onClick={create}><UserPlus size={16}/>Nuovo giocatore</button>}</div></div>
      <p className="club-role-note"><ShieldCheck size={15}/>R = lettura · W = scrittura · A = amministratore. Solo gli amministratori cambiano i ruoli, resettano password ed eliminano record.</p>
      <div className="table-scroll"><table className="club-table"><thead><tr><th>Giocatore</th><th>Squadra</th><th>Potenziale</th><th>Ruolo</th><th>Accesso</th><th>Azioni</th></tr></thead><tbody>{filteredPlayers.map(p=><tr key={p.id}>
        <td>{admin?<input aria-label={`Nome ${p.name}`} value={drafts[p.id]?.name??p.name} onChange={e=>patch(p.id,{name:e.target.value})}/>:p.name}</td>
        <td>{admin?<input aria-label={`Squadra ${p.name}`} value={drafts[p.id]?.team??p.team} onChange={e=>patch(p.id,{team:e.target.value})}/>:p.team}</td>
        <td>{admin?<input aria-label={`Potenziale ${p.name}`} type="number" min={1} max={10} value={drafts[p.id]?.potential??p.potential} onChange={e=>patch(p.id,{potential:Number(e.target.value)})}/>:p.potential}</td>
        <td>{admin?<select aria-label={`Ruolo ${p.name}`} value={drafts[p.id]?.role??p.role} onChange={e=>patch(p.id,{role:e.target.value as Role})}>{(['R','W','A'] as Role[]).map(role=><option key={role} value={role}>{roleName[role]}</option>)}</select>:roleName[p.role]}</td>
        <td>{p.password_set?'Attivo':'Da attivare'}</td><td>{canWrite&&<button className="text-button" onClick={()=>edit(p)}>Modifica</button>}</td>
      </tr>)}</tbody></table>{!filteredPlayers.length&&<div className="empty">Nessun giocatore trovato.</div>}</div>
      {admin&&Object.keys(drafts).length>0&&<div className="club-save"><span>{Object.keys(drafts).length} righe modificate</span><button className="secondary" disabled={busy} onClick={()=>setDrafts({})}>Annulla</button><button className="primary" disabled={busy||players.some(p=>{const d=drafts[p.id];return !!d&&(!String(d.name??p.name).trim()||!Number.isInteger(d.potential??p.potential)||(d.potential??p.potential)<1||(d.potential??p.potential)>10);})} onClick={()=>void saveTable()}><Save size={16}/>Salva modifiche tabella</button></div>}
    </section>}
    {tab==='palmares'&&<section className="results-card club-section"><div className="section-heading"><div><h2>Palmarès giocatori</h2><p>Campionati, gironi delle fasi finali ed eliminazione diretta.</p></div><Trophy/></div><div className="table-scroll"><table><thead><tr><th>Giocatore</th><th>🏆 Totale</th><th>🥇 Campionati</th><th>🏅 Gironi FF</th><th>⚡ Eliminazione</th></tr></thead><tbody>{sortedPalmares.map(p=><tr key={p.id}><td>{p.name}</td><td className="points">{totalTrophies(p)}</td><td>{p.NCampionatiVinti}</td><td>{p.NGironiFFVinti}</td><td>{p.NFFElimDirettaVinte}</td></tr>)}</tbody></table></div><label className="club-detail-select">Dettaglio trofei giocatore<select value={detail} onChange={e=>setDetail(e.target.value)}><option value="">Seleziona un giocatore</option>{players.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>{chosen&&<div className="club-trophies">{([['Campionati vinti',chosen.NCampionatiVinti,chosen.listaCampionatiVinti],['Gironi FF vinti',chosen.NGironiFFVinti,chosen.listaGironiFFVinti],['Eliminazione diretta',chosen.NFFElimDirettaVinte,chosen.listaFFElimDirettaVinte]] as [string,number,string[]][]).map(([label,count,names])=><div key={label}><strong>{count}</strong><span>{label}</span><p>{names.length?names.join(', '):'Nessun torneo registrato'}</p></div>)}</div>}</section>}
    {tab==='tournaments'&&<section className="results-card club-section"><div className="section-heading"><div><h2>Gestione tornei</h2><p>Archivio italiano e svizzero. Le eliminazioni globali escludono sempre i Campionati.</p></div></div>{(['italiana','svizzero'] as const).map(scope=><div className="club-tournament-group" key={scope}><h3>{scope==='italiana'?'🇮🇹 Tornei all’italiana':'🇨🇭 Tornei svizzeri'} <small>({tournaments.filter(t=>t.scope===scope).length})</small></h3><div className="club-tournament-list">{tournaments.filter(t=>t.scope===scope).map(t=><label key={selectionKey(t)} className="checkbox"><input type="checkbox" disabled={!admin} checked={selected.includes(selectionKey(t))} onChange={e=>setSelected(current=>e.target.checked?[...current,selectionKey(t)]:current.filter(x=>x!==selectionKey(t)))}/><span>{t.name}</span>{t.championship&&<small>Campionato</small>}</label>)}{!tournaments.some(t=>t.scope===scope)&&<div className="empty">Nessun torneo trovato.</div>}</div></div>)}{admin&&<div className="club-delete-actions"><button className="secondary" disabled={!selected.length||busy} onClick={()=>prepareDelete(tournaments.filter(t=>selected.includes(selectionKey(t))))}>Elimina {selected.length} selezionati</button><button className="secondary" disabled={busy||!tournaments.some(t=>t.scope==='italiana'&&!t.championship)} onClick={()=>prepareDelete(tournaments.filter(t=>t.scope==='italiana'&&!t.championship),true,'italiana')}>Cancella tutti gli italiani non Campionati</button><button className="secondary" disabled={busy||!tournaments.some(t=>t.scope==='svizzero'&&!t.championship)} onClick={()=>prepareDelete(tournaments.filter(t=>t.scope==='svizzero'&&!t.championship),true,'svizzero')}>Cancella tutti gli svizzeri non Campionati</button><button className="secondary" disabled={busy||!tournaments.some(t=>!t.championship)} onClick={()=>prepareDelete(tournaments.filter(t=>!t.championship),true,'all')}>Cancella tutti i tornei non Campionati</button></div>}</section>}
    {user.role==='A'&&<div className="legacy-note"><span>La versione classica resta disponibile durante la migrazione.</span><button className="text-button" onClick={onLegacy}>Apri versione classica<ArrowUpRight size={15}/></button></div>}
    {form&&<div className="modal-backdrop"><section className="modal club-modal" role="dialog" aria-modal="true" aria-label={form.id?'Modifica giocatore':'Nuovo giocatore'}><div className="section-heading"><h2>{form.id?'Modifica giocatore':'Nuovo giocatore'}</h2><button aria-label="Chiudi" disabled={busy} onClick={()=>setForm(null)}><X/></button></div><form onSubmit={e=>{e.preventDefault();void savePlayer();}}><label>Nome giocatore<input required maxLength={160} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Squadra<input maxLength={100} value={form.team} onChange={e=>setForm({...form,team:e.target.value})}/></label><label>Potenziale<input type="number" min={1} max={10} required value={form.potential} onChange={e=>setForm({...form,potential:Number(e.target.value)})}/></label><label>Ruolo{admin?<select value={form.role} onChange={e=>setForm({...form,role:e.target.value as Role})}>{(['R','W','A'] as Role[]).map(role=><option key={role} value={role}>{roleName[role]}</option>)}</select>:<input value={roleName[form.role]} disabled/>}</label><div className="modal-actions"><button type="button" className="secondary" disabled={busy} onClick={()=>setForm(null)}>Annulla</button><button className="primary" disabled={busy||!form.name.trim()||form.potential<1||form.potential>10}>Salva</button></div></form>{form.id&&admin&&<div className="club-admin-actions"><button className="secondary" disabled={busy} onClick={()=>{const p=players.find(x=>x.id===form.id);if(p)void resetPassword(p);}}>Reset password</button><button className="secondary danger" disabled={busy||form.id===user.id} onClick={()=>{const p=players.find(x=>x.id===form.id);if(p)void deletePlayer(p);}}>Elimina giocatore</button></div>}</section></div>}
    {deletion&&<div className="modal-backdrop"><section className="modal club-modal" role="dialog" aria-modal="true" aria-label="Conferma eliminazione tornei"><div className="section-heading"><h2>Conferma eliminazione</h2><button aria-label="Chiudi" disabled={busy} onClick={()=>setDeletion(null)}><X/></button></div><p>Stai per eliminare {deletion.targets.length} tornei: {deletion.targets.slice(0,5).map(t=>t.name).join(', ')}{deletion.targets.length>5?'…':''}.</p>{deletion.allExceptChampionships&&<p>I Campionati rimarranno nell’archivio.</p>}{needsPassword&&<label>Password del tuo account<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>}<label>Scrivi ELIMINA per confermare<input value={confirmation} onChange={e=>setConfirmation(e.target.value)} autoComplete="off"/></label><div className="modal-actions"><button className="secondary" disabled={busy} onClick={()=>setDeletion(null)}>Annulla</button><button className="primary danger" disabled={busy||confirmation!=='ELIMINA'||(needsPassword&&!password)} onClick={()=>void confirmDelete()}>Elimina tornei</button></div></section></div>}
  </>;
}
