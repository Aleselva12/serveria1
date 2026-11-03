export type Node = {id:string;title:string;parent?:string;role?:string;classification?:string;status?:string;priority?:string;note?:string;earlierNote?:string;trunkLinks?:string[];code?:string};
export const rank=['unknown','ok','plan','minor','problem'];
export function severity(n:Node, nodes:Node[], failures:Set<string>):string {
  const own=failures.has(n.id)?'problem':n.priority||'unknown';
  return nodes.filter(c=>c.parent===n.id).reduce((state,c)=>{
    const child=severity(c,nodes,failures);
    return rank.indexOf(child)>=3 && rank.indexOf(child)>rank.indexOf(state)?child:state;
  },own);
}
export const checks:Record<string,string[]>={
 'R2.1':['database'],B2:['library'],C3:['audio','audio_word_contract','audio_e2e'],B3:['word_sample'],
 'R3.1':['ollama'],A1:['chat_contract','chat_e2e'],C1:['calendar_contract','calendar_e2e'],worker:['worker_contract','worker_e2e'],
 T7:['memory_e2e'],B1:['files_e2e'],immich:['immich_e2e'],nextcloud:['nextcloud_e2e'],magazzino:['magazzino_e2e'],
 D4:['preventivi_e2e'],'R5.1':['backup_restore'],'R5.2':['updates_rollback']
};
