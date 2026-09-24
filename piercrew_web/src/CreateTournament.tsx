import React, {useEffect, useMemo, useRef, useState} from 'react';
import {ArrowLeft, ArrowRight, Plus, X} from 'lucide-react';
import {api, type Player, type Tournament} from './api';
import {BadgeEditor, type BadgeMap} from './TeamBadges';
import PlayerMultiSelect from './PlayerMultiSelect';

type Entry = {key:string; source_id:string|null; name:string; team:string; potential:number; guest:boolean};
type Override = {team:string; potential:number};

export default function CreateTournament({onClose,onCreated}:{onClose:()=>void;onCreated:(t:Tournament)=>void}) {
  const [step,setStep]=useState(1);
  const [name,setName]=useState('');
  const [players,setPlayers]=useState<Player[]>([]);
  const [selectedIds,setSelectedIds]=useState<string[]>([]);
  const [guestText,setGuestText]=useState('');
  const [search,setSearch]=useState('');
  const [usePlayerNames,setUsePlayerNames]=useState(false);
  const [overrides,setOverrides]=useState<Record<string,Override>>({});
  const [badgesByKey,setBadgesByKey]=useState<BadgeMap>({});
  const [badgeEditorOpen,setBadgeEditorOpen]=useState(false);
  const [groupCount,setGroupCount]=useState(1);
  const [assignment,setAssignment]=useState<'auto'|'manual'>('auto');
  const [manualGroups,setManualGroups]=useState<Record<string,number>>({});
  const [returns,setReturns]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const requestId=useRef(crypto.randomUUID());

  useEffect(()=>{api<Player[]>('/players').then(setPlayers).catch(e=>setError(e instanceof Error?e.message:'Impossibile caricare l’anagrafica.'));},[]);
  const guests=guestText.split('\n').map(s=>s.trim()).filter(Boolean);
  const entries:Entry[] = [
    ...players.filter(p=>selectedIds.includes(p.id)).map(p=>({key:p.id,source_id:p.id,name:p.name,
      team:overrides[p.id]?.team??(usePlayerNames?p.name:p.team),potential:overrides[p.id]?.potential??(Number(p.potential)||4),guest:false})),
    ...guests.map((guest,i)=>({key:`guest:${i}`,source_id:null,name:guest,
      team:overrides[`guest:${i}`]?.team??guest,potential:overrides[`guest:${i}`]?.potential??4,guest:true}))
  ];
  const labels=entries.map(e=>e.team.trim()?`${e.team.trim()} - ${e.name}`:e.name);
  const badges=Object.fromEntries(entries.flatMap((entry,i)=>badgesByKey[entry.key]?[[labels[i],badgesByKey[entry.key]]]:[])) as BadgeMap;
  const duplicateNames=new Set(entries.map(e=>e.name.toLocaleLowerCase())).size!==entries.length;
  const duplicateLabels=new Set(labels.map(x=>x.toLocaleLowerCase())).size!==labels.length;
  const validEntries=entries.length>=3&&entries.length<=64&&!duplicateNames&&!duplicateLabels&&entries.every(e=>Number.isInteger(e.potential)&&e.potential>=1&&e.potential<=10);
  const groups=useMemo(()=>{
    const result:Entry[][]=Array.from({length:groupCount},()=>[]);
    const ordered=assignment==='auto'?[...entries].sort((a,b)=>b.potential-a.potential):entries;
    ordered.forEach((entry,i)=>result[assignment==='auto'?i%groupCount:(manualGroups[entry.key]??i%groupCount)%groupCount].push(entry));
    return result;
  },[entries.map(e=>`${e.key}:${e.team}:${e.potential}`).join('|'),groupCount,assignment,JSON.stringify(manualGroups)]);
  const canGenerate=validEntries&&groups.every(g=>g.length>=2)&&!busy;
  function toggle(id:string){setSelectedIds(current=>current.includes(id)?current.filter(x=>x!==id):[...current,id]);}
  function update(entry:Entry,change:Partial<Override>){setOverrides(current=>({...current,[entry.key]:{team:change.team??entry.team,potential:change.potential??entry.potential}}));}
  function togglePlayerNames(checked:boolean){
    setUsePlayerNames(checked);
    setOverrides(current=>Object.fromEntries(entries.map(entry=>[entry.key,{team:checked?entry.name:(players.find(p=>p.id===entry.key)?.team??entry.name),potential:current[entry.key]?.potential??entry.potential}])));
  }
  async function submit(){
    setError('');
    if(!canGenerate)return;
    setBusy(true);
    try{
      const payload={name,groups:groups.map(g=>g.map(p=>p.team.trim()?`${p.team.trim()} - ${p.name}`:p.name)),
        participants:entries.map(({source_id,name,team,potential,guest})=>({source_id,name,team:team.trim(),potential,guest})),
        badges,return_matches:returns,request_id:requestId.current};
      onCreated(await api<Tournament>('/tournaments','POST',payload));
    }catch(e){setError(e instanceof Error?e.message:'Impossibile creare il torneo.');}
    finally{setBusy(false);}
  }

  return <div className="modal-backdrop"><section className="modal creation-modal" role="dialog" aria-modal="true" aria-labelledby="create-title">
    <div className="section-heading"><div><span className="eyebrow">NUOVO CAMPIONATO · PASSO {step} DI 3</span><h2 id="create-title">Crea un torneo all’italiana</h2></div><button aria-label="Chiudi" disabled={busy} onClick={onClose}><X/></button></div>
    {error&&<div role="alert" className="alert error">{error}</div>}
    <form onSubmit={e=>{e.preventDefault();if(step===3)void submit();}}>
      {step===1&&<>
        <label>Nome del torneo<input required maxLength={160} value={name} onChange={e=>setName(e.target.value)} placeholder="Nome del campionato"/></label>
        <div className="creation-options"><label>Numero di gironi<select value={groupCount} onChange={e=>setGroupCount(Number(e.target.value))}>{Array.from({length:8},(_,i)=><option key={i} value={i+1}>{i+1}</option>)}</select></label><label>Calendario<select value={returns?'return':'single'} onChange={e=>setReturns(e.target.value==='return')}><option value="single">Solo andata</option><option value="return">Andata e ritorno</option></select></label></div>
        <section className="creation-section"><h3>Giocatori del Club PierCrew</h3><p>Seleziona almeno tre partecipanti. Puoi usare il menu multiselezione o le checkbox: la scelta è condivisa.</p><PlayerMultiSelect players={players} selected={selectedIds} onChange={setSelectedIds}/><label className="checkbox"><input type="checkbox" checked={players.length>0&&selectedIds.length===players.length} onChange={e=>setSelectedIds(e.target.checked?players.map(p=>p.id):[])}/>Importa tutti i giocatori del Club</label><input aria-label="Cerca giocatore" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Cerca giocatore o squadra…"/><div className="player-picker">{players.filter(p=>`${p.name} ${p.team}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(p=><label key={p.id} className="checkbox"><input type="checkbox" checked={selectedIds.includes(p.id)} onChange={()=>toggle(p.id)}/><span>{p.name}<small>{p.team} · potenziale {p.potential}</small></span></label>)}</div></section>
        <section className="creation-section"><h3>Giocatori ospiti</h3><p>Inserisci un nome per riga. Gli ospiti partecipano al torneo ma non vengono aggiunti all’anagrafica.</p><textarea rows={3} aria-label="Giocatori ospiti" value={guestText} onChange={e=>setGuestText(e.target.value)} placeholder="Un ospite per riga"/></section>
        <div className="creation-count">{entries.length} partecipanti selezionati{duplicateNames?' · ci sono nomi duplicati':''}</div>
      </>}
      {step===2&&<>
        <p>Puoi modificare squadra e potenziale per questo torneo. L’anagrafica del Club non cambia.</p>
        <label className="checkbox"><input type="checkbox" checked={usePlayerNames} onChange={e=>togglePlayerNames(e.target.checked)}/>Usa i nomi dei giocatori come nomi delle squadre</label>
        <div className="participant-editor">{entries.map(entry=><div className="participant-row" key={entry.key}><strong>{entry.name}{entry.guest&&<small> ospite</small>}</strong><label>Squadra<input value={entry.team} maxLength={100} onChange={e=>update(entry,{team:e.target.value})}/></label><label>Potenziale<input type="number" min={1} max={10} value={entry.potential} onChange={e=>update(entry,{potential:Number(e.target.value)})}/></label></div>)}</div>
        <button type="button" className="secondary" onClick={()=>setBadgeEditorOpen(true)}>🛡️ Immagini per la vista Premium</button>
        {duplicateLabels&&<div role="alert" className="alert error">Due partecipanti avrebbero lo stesso nome nel calendario. Modifica le squadre.</div>}{entries.some(e=>e.potential<1||e.potential>10||!Number.isInteger(e.potential))&&<div role="alert" className="alert error">Il potenziale deve essere un numero intero tra 1 e 10.</div>}
      </>}
      {step===3&&<>
        <div className="creation-options">{groupCount>1&&<label>Distribuzione gironi<select value={assignment} onChange={e=>setAssignment(e.target.value as 'auto'|'manual')}><option value="auto">Automatica per potenziale</option><option value="manual">Manuale</option></select></label>}<label>Calendario<select value={returns?'return':'single'} onChange={e=>setReturns(e.target.value==='return')}><option value="single">Solo andata</option><option value="return">Andata e ritorno</option></select></label></div>
        <p>{groupCount===1?'Tutti i partecipanti giocano nello stesso calendario.':assignment==='auto'?'I giocatori sono ordinati per potenziale e distribuiti a turno nei gironi.':'Assegna ogni partecipante a un girone. Servono almeno due giocatori per girone.'}</p>
        {groupCount>1&&assignment==='manual'&&<div className="manual-assignments">{entries.map((entry,i)=><label key={entry.key}>{entry.name}<select value={manualGroups[entry.key]??i%groupCount} onChange={e=>setManualGroups(current=>({...current,[entry.key]:Number(e.target.value)}))}>{Array.from({length:groupCount},(_,g)=><option value={g} key={g}>Girone {g+1}</option>)}</select></label>)}</div>}
        <div className="group-preview">{groups.map((group,i)=><section className="group-editor" key={i}><h3>{groupCount>1?`Girone ${i+1}`:"Partecipanti"} <small>· potenziale medio {group.length?(group.reduce((n,p)=>n+p.potential,0)/group.length).toFixed(1):'0'}</small></h3>{group.map(p=><div key={p.key}>{p.team.trim()?`${p.team.trim()} - ${p.name}`:p.name} <small>· {p.potential}★</small></div>)}{group.length<2&&<p>Servono almeno due partecipanti.</p>}</section>)}</div>
      </>}
      <div className="modal-actions"><button type="button" className="secondary" disabled={busy} onClick={step===1?onClose:()=>setStep(step-1)}>{step===1?'Annulla':<><ArrowLeft size={16}/>Indietro</>}</button>{step<3?<button type="button" className="primary" disabled={step===1?(!name.trim()||!validEntries||entries.length<groupCount*2):!validEntries} onClick={()=>setStep(step+1)}>Continua<ArrowRight size={17}/></button>:<button type="button" className="primary" disabled={!canGenerate} onClick={()=>void submit()}>{busy?'Creazione…':<>Genera calendario<Plus size={17}/></>}</button>}</div>
    </form>
    {badgeEditorOpen&&<BadgeEditor participants={labels} badges={badges} busy={busy} onClose={()=>setBadgeEditorOpen(false)} onSave={async selected=>{setBadgesByKey(Object.fromEntries(entries.flatMap((entry,i)=>selected[labels[i]]?[[entry.key,selected[labels[i]]]]:[])));setBadgeEditorOpen(false);}}/>}
  </section></div>;
}
