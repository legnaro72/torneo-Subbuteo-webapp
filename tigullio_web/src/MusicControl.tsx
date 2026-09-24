import {useEffect, useRef, useState} from 'react';
import {Volume2, VolumeX} from 'lucide-react';

const key='tigullio-background-music';

export default function MusicControl({src='/TraLeDita.mp3'}:{src?:string}){
  const audio=useRef<HTMLAudioElement>(null);
  const [enabled,setEnabled]=useState(()=>localStorage.getItem(key)==='on');
  useEffect(()=>{
    if(enabled){audio.current?.load();void audio.current?.play().catch(()=>setEnabled(false));}
    else audio.current?.pause();
    localStorage.setItem(key,enabled?'on':'off');
  },[enabled,src]);
  return <><button className="music-control" type="button" aria-label={enabled?'Disabilita musica di sottofondo':'Abilita musica di sottofondo'} title={enabled?'Disabilita musica di sottofondo':'Abilita musica di sottofondo'} aria-pressed={enabled} onClick={()=>setEnabled(value=>!value)}>{enabled?<Volume2 size={17}/>:<VolumeX size={17}/>}<span>Musica {enabled?'attiva':'spenta'}</span></button><audio ref={audio} src={src} loop preload="none"/></>;
}
