import {useEffect, useRef, useState} from 'react';
import {ChevronDown, Search} from 'lucide-react';
import type {Player} from './api';

export default function PlayerMultiSelect({players,selected,onChange}:{players:Player[];selected:string[];onChange:(ids:string[])=>void}) {
  const [open,setOpen]=useState(false);
  const [query,setQuery]=useState('');
  const root=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!open)return;
    const close=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener('pointerdown',close);
    return()=>document.removeEventListener('pointerdown',close);
  },[open]);
  const matches=players.filter(player=>`${player.name} ${player.team}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const toggle=(id:string)=>onChange(selected.includes(id)?selected.filter(value=>value!==id):[...selected,id]);
  return <div className="player-multiselect" ref={root}>
    <button type="button" className="player-multiselect-toggle" aria-label="Seleziona più giocatori" aria-expanded={open} onClick={()=>setOpen(value=>!value)}>
      <span>{selected.length?`${selected.length} ${selected.length===1?'giocatore selezionato':'giocatori selezionati'}`:'Seleziona più giocatori…'}</span><ChevronDown size={17}/>
    </button>
    {open&&<div className="player-multiselect-menu">
      <label className="player-multiselect-search"><Search size={15}/><input autoFocus aria-label="Cerca nella multiselezione" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Cerca giocatore o squadra…"/></label>
      <div className="player-multiselect-options">{matches.map(player=><label className="checkbox" key={player.id}><input type="checkbox" checked={selected.includes(player.id)} onChange={()=>toggle(player.id)}/><span>{player.name}<small>{player.team}</small></span></label>)}{!matches.length&&<p>Nessun giocatore trovato.</p>}</div>
      <button type="button" className="text-button" onClick={()=>setOpen(false)}>Chiudi selezione</button>
    </div>}
  </div>;
}
