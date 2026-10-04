import { hashFile } from "./fileHash";
import { mediaRequest, MediaError } from "./mediaApi";
import { authenticatedFetch } from "./transport";
import { apiBaseUrl, ApiError } from "./api";
import type {
  FileArea,
  BrowserNode,
  BrowserRoot,
  BrowserListing,
  TrashItem,
} from "../types/contracts";

const prefix = (area: FileArea) =>
  area === "server" ? "/api/v1/server/files" : "/api/v1/library/files";
const query = (values: Record<string, string | number>) =>
  new URLSearchParams(
    Object.entries(values).map(([key, value]) => [key, String(value)]),
  ).toString();

async function fetchFile(
  area: FileArea,
  route: string,
  token: string,
  init: RequestInit = {},
  binary = false,
) {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    init.method === "POST" || binary ? 300000 : 15000,
  );
  try {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", "Bearer " + token);
    if (typeof init.body === "string")
      headers.set("Content-Type", "application/json");
    const response = await authenticatedFetch(apiBaseUrl + prefix(area) + route, {
      ...init,
      headers,
      signal: controller.signal,
    });
    if (!response.ok) {
      let detail = "Operazione non riuscita (HTTP " + response.status + ").";
      try {
        const data = await response.json();
        if (typeof data.detail === "string") detail = data.detail;
      } catch {
        /* Proxy may return an HTML error. */
      }
      if (response.status === 401)
        detail = "Token non valido. Inserisci il token di accesso ai file.";
      throw new ApiError(detail, "http", response.status);
    }
    if (binary) return response;
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError(
        "Risposta file non valida. Verifica la connessione al backend.",
        "invalid",
      );
    return response;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      controller.signal.aborted
        ? "Tempo di attesa scaduto: esito non confermato. Aggiorna l’elenco prima di riprovare."
        : "Collegamento non riuscito: backend non raggiungibile.",
      "offline",
    );
  } finally {
    clearTimeout(timer);
  }
}
async function json<T>(
  area: FileArea,
  route: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetchFile(area, route, token, init);
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("Risposta file non valida.", "invalid");
  }
}
const validNode = (n: BrowserNode) =>
  n &&
  typeof n.path === "string" &&
  typeof n.name === "string" &&
  ["file", "folder", "link", "special"].includes(n.kind) &&
  Array.isArray(n.capabilities) &&
  (n.sizeBytes === null ||
    (Number.isFinite(n.sizeBytes) && n.sizeBytes >= 0)) &&
  Number.isFinite(Date.parse(n.modifiedAt));
export const filesApi = {
  async roots(area: FileArea, token: string): Promise<BrowserRoot[]> {
    const data = await json<{ roots: BrowserRoot[] }>(area, "/roots", token);
    if (
      !data ||
      !Array.isArray(data.roots) ||
      !data.roots.every(
        (r) =>
          r &&
          typeof r.id === "string" &&
          typeof r.label === "string" &&
          typeof r.writable === "boolean" &&
          typeof r.available === "boolean",
      )
    )
      throw new ApiError("Risorse del server non valide.", "invalid");
    return data.roots;
  },
  async children(
    area: FileArea,
    token: string,
    rootId: string,
    path: string,
    search = "",
    offset = 0,
    recursive = false,
  ): Promise<BrowserListing> {
    const data = await json<BrowserListing>(
      area,
      (recursive && search ? "/search?" : "/children?") +
        query({ root_id: rootId, path, query: search, offset, limit: 100 }),
      token,
    );
    if (
      !data ||
      !Array.isArray(data.items) ||
      !data.items.every(validNode) ||
      !Number.isInteger(data.total) ||
      data.total < 0 ||
      typeof data.writable !== "boolean" ||
      data.rootId !== rootId ||
      data.path !== path
    )
      throw new ApiError("Elenco dei file non valido.", "invalid");
    return data;
  },
  async trashList(
    area: FileArea,
    token: string,
    rootId: string,
  ): Promise<TrashItem[]> {
    const data = await json<{ items: TrashItem[] }>(
      area,
      "/trash?" + query({ root_id: rootId }),
      token,
    );
    if (
      !data ||
      !Array.isArray(data.items) ||
      !data.items.every(
        (i) =>
          i &&
          typeof i.id === "string" &&
          typeof i.path === "string" &&
          Number.isFinite(Date.parse(i.deletedAt)),
      )
    )
      throw new ApiError("Cestino non valido.", "invalid");
    return data.items;
  },
  mutate(area: FileArea, token: string, route: string, body: object) {
    return json(area, route, token, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  upload(
    area: FileArea,
    token: string,
    rootId: string,
    path: string,
    file: File,
  ) {
    const form = new FormData();
    form.set("root_id", rootId);
    form.set("path", path);
    form.set("file", file);
    return json(area, "/upload", token, { method: "POST", body: form });
  },
  async preview(area:FileArea, token:string, rootId:string, item:BrowserNode) {
    const response=await fetchFile(area,"/preview?"+query({root_id:rootId,path:item.path}),token,{},true);
    if(response.headers.get("content-type")?.includes("application/json")) {
      const data=await response.json();
      if(data.kind!=="text" || typeof data.text!=="string")throw new Error("Anteprima non valida.");
      return {kind:"text",text:data.text,truncated:Boolean(data.truncated),url:"",mime:""};
    }
    const blob=await response.blob();
    return {kind:"media",text:"",truncated:false,url:URL.createObjectURL(blob),mime:blob.type};
  },
  shares(area:FileArea,rootId:string) {
    return mediaRequest<{items:{id:string;path:string;expiresAt:string;revoked:boolean}[]}>(prefix(area)+"/shares?"+query({root_id:rootId}));
  },
  share(area:FileArea,rootId:string,path:string,hours=24) {
    return mediaRequest<{id:string;url:string;expiresAt:string;requiresLogin:boolean}>(prefix(area)+"/shares",{method:"POST",body:JSON.stringify({root_id:rootId,path,hours})});
  },
  revokeShare(area:FileArea,id:string) {return mediaRequest(prefix(area)+"/shares/"+id,{method:"DELETE"});},
  async resumableUpload(area:FileArea,rootId:string,path:string,file:File,progress:(text:string)=>void) {
    const storageKey="cora-upload:"+area+":"+rootId+":"+path+":"+file.name+":"+file.size;
    progress("Verifica del file…");
    const digest=await hashFile(file,p=>progress(`Verifica del file ${p}%`));
    type UploadState={id:string;offset:number;size:number;sha256:string};
    let session:UploadState|null=null;
    const previous=localStorage.getItem(storageKey);
    if(previous){
      // A stored ID is scoped to this area/root. Expired sessions can safely start again.
      try{session=await mediaRequest<UploadState>(prefix(area)+"/uploads/"+previous+"?"+query({root_id:rootId}));}
      catch(e){if(e instanceof MediaError && [404,410].includes(e.status))localStorage.removeItem(storageKey);else throw e;}
      if(session&&session.sha256!==digest)throw new Error("Il file è diverso dall’upload in sospeso. Annulla l’upload precedente prima di caricarne un altro con questo nome.");
    }
    if(!session){session=await mediaRequest<UploadState>(prefix(area)+"/uploads",{method:"POST",body:JSON.stringify({root_id:rootId,path,filename:file.name,size:file.size,sha256:digest})});localStorage.setItem(storageKey,session.id);}
    while(session.offset<file.size){
      if(!Number.isInteger(session.offset)||session.offset<0)throw new Error("Offset upload non valido.");
      const form=new FormData();form.set("root_id",rootId);form.set("offset",String(session.offset));form.set("file",file.slice(session.offset,session.offset+4*1024*1024),file.name);
      session=await mediaRequest<UploadState>(prefix(area)+"/uploads/"+session.id+"/chunks",{method:"POST",body:form});
      progress(`Caricamento ${Math.round(session.offset/file.size*100)}%`);
    }
    progress("Salvataggio sul server…");
    const result=await mediaRequest(prefix(area)+"/uploads/"+session.id+"/complete?"+query({root_id:rootId}),{method:"POST"});
    localStorage.removeItem(storageKey);return result;
  },
  async cancelPendingUploads(area:FileArea,rootId:string,path:string) {
    const starts="cora-upload:"+area+":"+rootId+":"+path+":";
    for(const key of Object.keys(localStorage).filter(k=>k.startsWith(starts))){const id=localStorage.getItem(key);if(id){try{await mediaRequest(prefix(area)+"/uploads/"+id+"?"+query({root_id:rootId}),{method:"DELETE"});}catch(e){if(!(e instanceof MediaError)||![404,410].includes(e.status))throw e;}}localStorage.removeItem(key);}
  },
  async download(
    area: FileArea,
    token: string,
    rootId: string,
    item: BrowserNode,
  ) {
    const response = await fetchFile(
      area,
      "/download?" + query({ root_id: rootId, path: item.path }),
      token,
      {},
      true,
    );
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = item.name;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },
};

