export type DirectTournament = {type:string; name:string};

export function tournamentPath(name:string,type='italiana'){
  if(name.includes('/'))return `/?tipo=${encodeURIComponent(type)}&torneo=${encodeURIComponent(name)}`;
  return `/torneo/${encodeURIComponent(type)}/${encodeURIComponent(name)}`;
}

export function readTournamentRoute(location:Pick<Location,'pathname'|'search'>):DirectTournament|null{
  const parts=location.pathname.split('/').filter(Boolean);
  if(parts.length===3&&parts[0]==='torneo'){
    try{const name=decodeURIComponent(parts[2]);return name?{type:parts[1],name}:null;}catch{return null;}
  }
  const params=new URLSearchParams(location.search);
  const type=params.get('tipo');
  const name=params.get('torneo')||params.get('nome');
  return type&&name?{type,name}:null;
}
