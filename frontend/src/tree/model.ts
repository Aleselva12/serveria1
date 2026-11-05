export type Node = {
  id:string;title:string;parent?:string;role?:string;classification?:string;
  status?:string;priority?:string;note?:string;earlierNote?:string;trunkLinks?:string[];
  code?:string;knownIssues?:string[];roadmapRefs?:string[];
  observations?:Array<{text:string;type?:string;commit?:string|null;observedAt?:string|null}>;
  timeline?:{past?:Array<{text?:string;commit?:string;at?:string}>;present?:{statement?:string;source?:string;runtimeVerified?:boolean};future?:string[]};
};
export const rank=["unknown","ok","plan","minor","problem"];
/** Historical primitive retained for old coverage; run evidence and status use distinct helpers in TreeHome. */
export function severity(n:Node,nodes:Node[],failures:Set<string>):string {
  const own=failures.has(n.id)?"problem":n.priority||"unknown";
  return nodes.filter(c=>c.parent===n.id).reduce((state,c)=>{
    const child=severity(c,nodes,failures);
    return rank.indexOf(child)>=3&&rank.indexOf(child)>rank.indexOf(state)?child:state;
  },own);
}
/** References only the pre-existing shared health catalog; never runs checks from the map. */
export const checks:Record<string,string[]>={
  "R1.2.p2":["desktop_e2e"],"R1.2.p2.m2":["desktop_e2e"],"R1.2.p3.m1":["desktop_e2e"],
  "R1.3.p2":["laptop_e2e"],
  "T1.p1":["chat_contract","chat_e2e"],"T1.p1.m2":["chat_e2e"],
  "T6.p1":["memory_regression"],"T6.p1.m1":["memory_regression"],"T6.p1.m2":["memory_regression"],
  "T8.p3":["worker_e2e"],"T8.p3.m1":["worker_e2e"],"T8.p3.m2":["worker_e2e"],
  "B1.p2.m1":["files_e2e"],"B1.p2.m2":["files_regression"],"B1.p3.m2":["files_regression"],
  "C1b.m1":["calendar_regression"],"C1b.m2":["calendar_regression"],
  "R1.2":["worker_contract","desktop_e2e"],"R1.3":["worker_contract","laptop_e2e"],
  "R2.1":["database"],"B2":["library"],"C3":["audio","audio_word_contract","audio_e2e"],
  "B3":["word_sample"],"R3.1":["ollama"],
  "A1":["chat_contract","chat_e2e"],"T1":["chat_contract","orchestrator_v1_contract","orchestration_regression","chat_e2e"],
  "T2":["orchestrator_v1_contract"],"T3":["orchestrator_v1_contract"],"T4":["orchestrator_v1_contract"],
  "T5":["orchestrator_v1_contract"],"T6":["orchestrator_v1_contract"],
  "T10":["orchestrator_v1_contract","chat_e2e"],"T11":["orchestrator_v1_contract","chat_contract","audio_word_contract"],
  "C1":["calendar_contract","calendar_regression","calendar_e2e"],"C1a":["calendar_contract"],"C1b":["calendar_e2e"],
  "C2":["gmail_contract","gmail_e2e"],
  "worker":["worker_contract","worker_e2e"],"T8":["worker_contract","worker_e2e"],
  "installare":["worker_contract"],"assegnare":["worker_e2e"],
  "T7":["memory_regression","memory_e2e"],"B1":["files_regression","files_e2e"],"C3.p4":["audio_e2e"],
  "immich":["immich_e2e"],"nextcloud":["nextcloud_e2e"],"magazzino":["magazzino_e2e"],
  "D4":["preventivi_e2e"],"R5.1":["backup_restore"],"R5.2":["updates_rollback"],
};
