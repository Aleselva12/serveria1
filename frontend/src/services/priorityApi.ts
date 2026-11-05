import {apiBaseUrl} from "./api";
import {authenticatedFetch} from "./transport";

export type PriorityRating = {
  id:string; title?:string; score:number; explanation:string;
  importance:number;urgency:number;blockers:number;impact:number;effort:number;risk:number;
  confidence:"low"|"medium"|"high";
};
export type PriorityEvaluation = {
  model:string;reported_model?:string|null;model_verified?:boolean;provider?:string;
  evaluated_at?:string;objective_count?:number;ratings:PriorityRating[];warning:string;
  weights?:Record<string,number>;scoring_version?:string;persisted?:boolean;persistence_detail?:string;
  writes_map:false;
};
export type PriorityStatus = {
  model:string;installed:boolean;available:boolean;detail:string;provider?:string;
  configuration_source?:string;separate_from_supervisor?:boolean;weights?:Record<string,number>;
  max_objectives?:number;history_available?:boolean;
  last_evaluation?:Pick<PriorityEvaluation,"model"|"reported_model"|"model_verified"|"evaluated_at"|"objective_count">|null;
};
async function get<T>(suffix:string):Promise<T>{
  const response=await authenticatedFetch(apiBaseUrl+"/api/v1/roadmap/classifier/"+suffix,{signal:AbortSignal.timeout(20000)});
  if(!response.ok)throw Error("Priorità non disponibili: verifica la connessione e l'aggiornamento del server.");
  return response.json() as Promise<T>;
}
export const priorityApi={
  async status(){
    const result=await get<PriorityStatus>("status");
    if(typeof result.model!=="string"||typeof result.installed!=="boolean"||typeof result.available!=="boolean")
      throw Error("Stato del modello priorità non valido.");
    return result;
  },
  async latest(){
    const result=await get<{evaluation:PriorityEvaluation|null;available:boolean}>("latest");
    if(typeof result.available!=="boolean"||!(result.evaluation===null||Array.isArray(result.evaluation?.ratings)))
      throw Error("Risultato delle priorità non valido.");
    return result;
  },
};
