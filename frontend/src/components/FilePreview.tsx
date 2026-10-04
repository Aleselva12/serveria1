import {useEffect,useState} from 'react';
import type {BrowserNode,FileArea} from '../types/contracts';
import {filesApi} from '../services/filesApi';
export default function FilePreview({area,rootId,item,token,close}:{area:FileArea;rootId:string;item:BrowserNode;token:string;close:()=>void}) {
  const [preview,setPreview]=useState<Awaited<ReturnType<typeof filesApi.preview>>|null>(null),[error,setError]=useState('');
  useEffect(()=>{let live=true,url='';void filesApi.preview(area,token,rootId,item).then(p=>{url=p.url;if(live)setPreview(p);else if(url)URL.revokeObjectURL(url);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;if(url)URL.revokeObjectURL(url);};},[area,rootId,item.path,token]);
  return <div className="file-modal-shade"><section className="file-modal media-preview" role="dialog" aria-modal="true" aria-label={'Anteprima '+item.name}><div className="metric-head"><h2>{item.name}</h2><button onClick={close} aria-label="Chiudi anteprima">×</button></div>{error&&<p role="alert">{error}</p>}{!preview&&!error&&<p role="status">Caricamento anteprima…</p>}{preview&&(preview.kind==='text'?<><pre>{preview.text}</pre>{preview.truncated&&<p>Anteprima limitata. Scarica il file per leggere tutto.</p>}</>:preview.mime.startsWith('image/')?<img src={preview.url} alt={item.name}/>:preview.mime.startsWith('audio/')?<audio controls src={preview.url}/>:preview.mime.startsWith('video/')?<video controls src={preview.url}/>:<iframe src={preview.url} title={item.name} sandbox="allow-same-origin"/>)}</section></div>;
}
