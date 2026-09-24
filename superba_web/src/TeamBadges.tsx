import {useEffect, useMemo, useState} from 'react';
import {Search, X} from 'lucide-react';

export type TeamBadge = {kind:'flag'|'club';ref:string;url?:string;credit?:string;license?:string};
export type BadgeMap = Record<string,TeamBadge>;

const codes = 'AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split(' ');
const regionNames = new Intl.DisplayNames(['it'],{type:'region'});
const countries = codes.map(code=>({code,name:regionNames.of(code)||code})).sort((a,b)=>a.name.localeCompare(b.name,'it'));
const flagUrl=(code:string)=>`https://flagcdn.com/${code.toLowerCase()}.svg`;
const normalized=(value:string)=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('it').trim();
export function automaticFlag(name:string):TeamBadge|undefined{
  const possible=[name.trim(),name.split(' - ')[0].trim(),name.includes('-')?name.slice(0,name.lastIndexOf('-')).trim():name.trim()];
  const country=countries.find(item=>possible.some(team=>normalized(item.name)===normalized(team)));
  return country?{kind:'flag',ref:country.code}:undefined;
}

export function TeamMark({name,badge}:{name:string;badge?:TeamBadge}){
  const [failed,setFailed]=useState(false);
  const shown=badge||automaticFlag(name);
  useEffect(()=>setFailed(false),[shown?.kind,shown?.ref,shown?.url]);
  const src=shown?.kind==='flag'?flagUrl(shown.ref):shown?.url;
  return src&&!failed?<img className={'team-badge '+shown?.kind} src={src} alt={shown?.kind==='flag'?`Bandiera ${regionNames.of(shown.ref)||shown.ref}`:`Immagine del club ${name}`} title={shown?.credit?`${name} · ${shown.credit}${shown.license?` · ${shown.license}`:''}`:name} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>:<>{name.slice(0,1)}</>;
}

type ClubResult={ref:string;name:string;description?:string;type:'logo'|'bandiera'|'stemma';source:string;url:string;credit:string;license:string};
function badgeSource(ref:string){
  if(ref.startsWith('File:'))return {url:`https://commons.wikimedia.org/wiki/${encodeURIComponent(ref.replace(/ /g,'_'))}`,label:'Fonte e licenza su Wikimedia Commons ↗'};
  if(ref.startsWith('football-logos:'))return {url:`https://github.com/JoseArroyave/football-logos/blob/main/${ref.slice('football-logos:'.length).split('/').map(encodeURIComponent).join('/')}`,label:'Archivio football-logos ↗'};
  if(ref.startsWith('sportmonks:'))return {url:'https://www.sportmonks.com/',label:'Fonte Sportmonks ↗'};
  return {url:'https://www.football-data.org/',label:'Fonte football-data.org ↗'};
}
async function searchClubLogos(query:string,signal:AbortSignal):Promise<ClubResult[]>{
  const response=await fetch(`/api/club-logos?q=${encodeURIComponent(query)}`,{signal,credentials:'same-origin'});
  if(!response.ok){const detail=await response.json().catch(()=>({}));throw new Error(detail.detail||'Ricerca stemmi non disponibile. Riprova.');}
  return response.json() as Promise<ClubResult[]>;
}

export function BadgeEditor({participants,badges,busy,error,onClose,onSave}:{participants:string[];badges:BadgeMap;busy:boolean;error?:string;onClose:()=>void;onSave:(badges:BadgeMap)=>Promise<void>}){
  const [draft,setDraft]=useState<BadgeMap>({...badges});
  const [selected,setSelected]=useState(participants[0]||'');
  const [kind,setKind]=useState<'flag'|'club'>(draft[selected]?.kind||'flag');
  const [flagQuery,setFlagQuery]=useState('');const [clubQuery,setClubQuery]=useState('');
  const [clubs,setClubs]=useState<ClubResult[]>([]);const [searchError,setSearchError]=useState('');const [searching,setSearching]=useState(false);
  const visibleCountries=useMemo(()=>countries.filter(c=>`${c.name} ${c.code}`.toLocaleLowerCase('it').includes(flagQuery.toLocaleLowerCase('it'))).slice(0,40),[flagQuery]);
  useEffect(()=>{
    if(kind!=='club'||clubQuery.trim().length<3){setClubs([]);setSearchError('');return;}
    const controller=new AbortController();const timer=window.setTimeout(()=>{
      setSearching(true);setSearchError('');searchClubLogos(clubQuery.trim(),controller.signal).then(setClubs).catch(e=>{if(!controller.signal.aborted)setSearchError(e instanceof Error?e.message:'Ricerca non riuscita.');}).finally(()=>{if(!controller.signal.aborted)setSearching(false);});
    },350);
    return()=>{window.clearTimeout(timer);controller.abort();};
  },[clubQuery,kind]);
  const current=draft[selected]||automaticFlag(selected);
  function choose(badge?:TeamBadge){setDraft(old=>{const next={...old};if(badge)next[selected]=badge;else delete next[selected];return next;});}
  return <div className="modal-backdrop"><section className="modal badge-modal" role="dialog" aria-modal="true" aria-label="Immagini Premium delle squadre">
    <div className="section-heading"><div><span className="eyebrow">VISTA PREMIUM</span><h2>🛡️ Bandiere e stemmi</h2><p>Le immagini compaiono solo nella vista Premium.</p></div><button aria-label="Chiudi" disabled={busy} onClick={onClose}><X/></button></div>
    <label>Partecipante<select value={selected} onChange={e=>{setSelected(e.target.value);setKind(draft[e.target.value]?.kind||'flag');}}>{participants.map(p=><option key={p}>{p}</option>)}</select></label>
    <div className="badge-current"><span className="team-mark"><TeamMark name={selected} badge={current}/></span><strong>{selected}</strong><span>{current?current.kind==='flag'?`${regionNames.of(current.ref)}${!draft[selected]?' · automatica':''}`:current.ref.replace(/^File:/,''):'Nessuna immagine'}</span><button type="button" className="secondary compact" disabled={!draft[selected]||busy} onClick={()=>choose()}>Rimuovi scelta</button></div>
    {current?.kind==='club'&&<a className="badge-source-link" href={badgeSource(current.ref).url} target="_blank" rel="noopener noreferrer">{badgeSource(current.ref).label}</a>}
    <div className="segmented badge-tabs"><button type="button" className={kind==='flag'?'active':''} onClick={()=>setKind('flag')}>🏳️ Bandiere</button><button type="button" className={kind==='club'?'active':''} onClick={()=>setKind('club')}>⚽ Stemmi club</button></div>
    {kind==='flag'?<><label className="search badge-search"><Search size={16}/><input aria-label="Cerca nazione" value={flagQuery} onChange={e=>setFlagQuery(e.target.value)} placeholder="Cerca una nazione…"/></label><div className="badge-results">{visibleCountries.map(c=><button type="button" key={c.code} className={current?.kind==='flag'&&current.ref===c.code?'selected':''} onClick={()=>choose({kind:'flag',ref:c.code})}><img src={flagUrl(c.code)} alt="" loading="lazy"/><span>{c.name}</span><small>{c.code}</small></button>)}</div></>:
      <><label className="search badge-search"><Search size={16}/><input aria-label="Cerca club calcistico" value={clubQuery} onChange={e=>setClubQuery(e.target.value)} placeholder="Cerca il nome del club (minimo 3 lettere)…"/></label><p className="badge-source">Ricerca combinata tra Wikimedia Commons, football-logos e le fonti API configurate. Bandiere e stemmi dei club compaiono se disponibili; verifica i diritti dell'immagine presso la fonte.</p>{searching&&<p>Ricerca in corso…</p>}{searchError&&<p role="alert">{searchError}</p>}{!searching&&!searchError&&clubQuery.trim().length>=3&&!clubs.length&&<p>Nessuna immagine trovata. Prova il nome completo del club.</p>}<div className="badge-results">{clubs.map(c=><button type="button" key={c.ref} className={current?.ref===c.ref?'selected':''} onClick={()=>choose({kind:'club',ref:c.ref,url:c.url,credit:c.credit,license:c.license})}><img src={c.url} alt="" loading="lazy"/><span>{c.name}<small>{c.type} · {c.source} · {c.description} · {c.license} · {c.credit}</small></span></button>)}</div></>}
    {error&&<div className="alert error" role="alert">{error}</div>}
    <div className="modal-actions"><button type="button" className="secondary" disabled={busy} onClick={onClose}>Annulla</button><button type="button" className="primary" disabled={busy} onClick={()=>void onSave(draft)}>{busy?'Salvataggio…':'Salva immagini'}</button></div>
  </section></div>;
}
