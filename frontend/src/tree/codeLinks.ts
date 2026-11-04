/** Explicit, reviewed source links — NOT inferred by an agent or a test.
 * Only paths that exist in their repositories belong in this registry.
 * Missing links mean "not yet mapped", not "code does not exist".
 */
export type SourceLink={repo?:string;ref?:string;path:string;label:string;purpose?:string};
const local=(path:string,label:string,purpose?:string):SourceLink=>({path,label,purpose});
const qwe=(path:string,label:string):SourceLink=>({repo:"Aleselva12/qwe",ref:"progetti/cora-serveria",path,label});
export const codeLinks:Record<string,SourceLink[]>={
 "R1.1":[local("core/monitoring.py","Monitoraggio host"),local("deploy/doctor.py","Diagnostica Debian")],
 "R1.2":[local("core/machines_api.py","Worker e macchine")],
 "R1.3":[local("core/machines_api.py","Worker e macchine")],
 "R2.1":[local("core/memory.py","Persistenza e memoria")],
 "R2.2":[local("core/library_monitor.py","Monitor filesystem")],
 "R3.1":[local("core/machines_api.py","Inferenza e worker"),local("core/project_checks.py","Prerequisiti Ollama e audio")],
 "R3.2":[local("frontend/src/components/Machines.tsx","Modelli e macchine")],
 "R4.1":[local("deploy/doctor.py","Verifica servizi e sistema")],
 "R4.2":[local("frontend/package.json","Dipendenze frontend")],
 "R5.1":[local("deploy/doctor.py","Controlli di preflight")],
 "R5.2":[local("frontend/src/components/SystemUpdate.tsx","Interfaccia aggiornamenti"),
           local("core/managed_apps_api.py","Applicazioni gestite")],
 "R6.1":[local("core/machines_api.py","Connessione dei worker")],
 "R6.2":[local("core/permissions.py","Motore autorizzazioni")],
 "T1":[local("core/orchestration.py","Contratti orchestrazione"),
       local("core/system_coordinator.py","Coordinator")],
 "T2":[local("core/orchestration.py","Tool e instradamento")],
 "T3":[local("core/system_coordinator.py","Stato coordinatore")],
 "T4":[local("core/runtime.py","Runtime")],
 "T5":[local("core/event_bus.py","Event Bus"),local("core/component_bus.py","Component Bus")],
 "T6":[local("core/orchestration.py","Contratti del flusso")],
 "T7":[local("core/memory.py","Gestione memoria"),local("frontend/src/components/MemoryManagement.tsx","Interfaccia memoria")],
 "T8":[local("frontend/src/components/Architecture.tsx","Configurazione agenti"),
       local("frontend/src/components/Machines.tsx","Modelli dei worker")],
 "T10":[local("core/monitoring.py","Monitoraggio e misure"),local("frontend/src/services/runtimeApi.ts","Tracce dal frontend")],
 "T11":[local("core/health_catalog.py","Catalogo condiviso dei controlli"),
       local("core/project_checks.py","Verifiche periodiche"),
       local("frontend/src/components/HealthDashboard.tsx","Dashboard verifiche")],
 "T12":[local("frontend/src/components/Home.tsx","Home ServerIA"),local("frontend/src/App.tsx","Navigazione principale")],
 "A1":[local("frontend/src/App.tsx","Chat e navigazione"),
       local("frontend/src/services/runtimeApi.ts","Richieste chat")],
 "A2":[local("frontend/src/App.tsx","Sessioni chat")],
 "B1":[local("frontend/src/components/FileManager.tsx","Gestione file")],
 "B2":[local("core/library_monitor.py","Libreria IA"),local("frontend/src/components/FileManager.tsx","Consultazione file")],
 "B3":[local("frontend/src/components/FileManager.tsx","Interfaccia documentale")],
 "C1":[local("frontend/src/components/Calendar.tsx","Calendario"),
       local("core/notifications.py","Notifiche")],
 "C3":[local("frontend/src/components/Audio.tsx","Audio")],
 "immich":[local("core/monitoring.py","Stato servizio Immich")],
 "nextcloud":[local("core/monitoring.py","Stato servizio Nextcloud")],
 "magazzino":[local("core/managed_apps_api.py","Ponte applicazioni gestite")],
 "D5":[qwe("cora-plan.json","Mappa Cora originale"),
       qwe("docs/CORA_MAPPA_V2_COMPLETA.md","Descrizione architetturale completa")],
 "worker":[local("core/machines_api.py","API worker"),
           local("frontend/src/components/Machines.tsx","Gestione e test worker")],
 "G1":[local("frontend/src/components/Programmer.tsx","Interfaccia programmatore")],
};
const pages:Record<string,{hash:string;label:string}>={
 "R1.1":{hash:"#home",label:"Apri Home"},"R3.2":{hash:"#machines",label:"Apri Macchine"},
 "R5.2":{hash:"#updates",label:"Apri Aggiornamenti"},
 T7:{hash:"#memory-management",label:"Apri Gestione Memoria"},
 T8:{hash:"#architecture",label:"Apri Architettura"},
 T10:{hash:"#activity",label:"Apri Attività"},
 T11:{hash:"#home",label:"Apri monitoraggio Home"},
 A1:{hash:"#chat",label:"Apri Chat"},
 B1:{hash:"#files",label:"Apri File"},
 B2:{hash:"#files",label:"Apri File"},
 B3:{hash:"#files",label:"Apri File"},
 C1:{hash:"#calendar",label:"Apri Calendario"},
 C3:{hash:"#audio",label:"Apri Audio"},
 worker:{hash:"#machines",label:"Apri Macchine"},
 G1:{hash:"#code",label:"Apri Programma"},
};
export const pageLinks=pages;
export function sourceUrl(link:SourceLink){
 const repo=link.repo||"Aleselva12/serveria1",ref=link.ref||"main";
 return "https://github.com/"+repo+"/blob/"+ref+"/"+link.path.split("/").map(encodeURIComponent).join("/");
}
