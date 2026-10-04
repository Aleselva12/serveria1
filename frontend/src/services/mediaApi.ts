import { authenticatedFetch } from './transport';
import { apiBaseUrl } from './api';

export class MediaError extends Error { constructor(message:string, public status:number){super(message);} }

export async function mediaRequest<T>(route:string, init:RequestInit = {}):Promise<T> {
  const headers = new Headers(init.headers);
  if (typeof init.body === 'string') headers.set('Content-Type','application/json');
  const response = await authenticatedFetch(apiBaseUrl + route, {...init, headers});
  if (!response.ok) {
    let detail = `Operazione non riuscita (HTTP ${response.status}).`;
    try { const data = await response.json(); if (typeof data.detail === 'string') detail = data.detail; } catch { /* no successful fallback */ }
    throw new MediaError(detail,response.status);
  }
  return response.json() as Promise<T>;
}
export type Attachment = {id:string; name:string; sizeBytes:number; truncated:boolean; downloadUrl:string};
export async function uploadAttachment(threadId:string, file:File) {
  const form = new FormData(); form.set('conversation_id',threadId); form.set('file',file);
  return mediaRequest<Attachment>('/api/v1/chat/attachments',{method:'POST',body:form});
}
export type AudioRecord = {
  id:string; title:string; name:string; recordedAt:string; speakerNames:string[]; createdAt:string;
  version:number; transcript:string|null; result:{diarization_status:string; diarization_warning:string|null; duration_seconds:number; detected_language:string}|null;
  run:{id:string;status:string}|null;
};
export async function downloadMedia(route:string, name:string) {
  const response = await authenticatedFetch(apiBaseUrl+route);
  if (!response.ok) throw new Error(`Download non riuscito (HTTP ${response.status}).`);
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement('a'); a.href=url; a.download=name; a.click();
  setTimeout(()=>URL.revokeObjectURL(url),60000);
}
