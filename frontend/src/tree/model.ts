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
  "assegnare.m2":["worker_e2e"],
  "C1.p6.m1":["calendar_e2e"],
  "C3.p4.m1":["word_document_regression"],
  "B3.p2.m2":["preventivi_e2e"],
  "B3.p2.m1":["preventivi_e2e"],
  "B3.p2":["preventivi_e2e"],
  "A1.p2.m2":["chat_e2e"],
  "A1.p2":["chat_e2e"],
  "T11.p4.m2":["audio_e2e", "calendar_regression", "agent_bindings_regression"],
  "T11.p4.m1":["chat_e2e"],
  "T2.p3.m1":["chat_e2e"],
  "R5.2.p1.m2":["updates_rollback"],
  "R5.2.p1.m1":["updates_rollback"],
  "R5.2.p1":["updates_rollback"],
  "R3.1.p1.m1":["ollama"],
  "R2.2.p2.m2":["files_regression"],
  "R2.2.p1.m2":["library_copy_regression"],
  "R2.1.p1":["database"],
  "R2.1.p3.m1":["migration_contract_regression"],
  "G1.p1.m2":["programmer_graph_regression"],
  "G1.p1.m1":["programmer_graph_regression"],
  "G1.p1":["programmer_graph_regression"],
  "G1.p3.m2":["programmer_workspace_regression"],
  "G1.p3.m1":["programmer_workspace_regression"],
  "G1.p3":["programmer_workspace_regression"],
  "G1.p2.m1":["programmer_workspace_regression"],
  "C3.p2.m1":["audio_engine_regression"],
  "R3.1.p2.m1":["audio_engine_regression"],
  "A2.p3.m1":["adaptive_context_regression"],
  "T6.p2.m2":["adaptive_context_regression"],
  "T6.p2.m1":["adaptive_context_regression"],
  "T6.p2":["adaptive_context_regression"],
  "T12.p4.m2":["provider_diagnostics_regression"],
  "T10.p2.m1":["provider_diagnostics_regression"],
  "T10.p2":["provider_diagnostics_regression"],
  "assegnare.m1":["model_selection_regression"],
  "worker.p3.m2":["machine_registry_regression"],
  "R1.3.p2.m1":["machine_registry_regression"],
  "R1.2.p2.m1":["machine_registry_regression"],
  "installare.m2":["machine_registry_regression"],
  "installare.m1":["machine_registry_regression"],
  "worker.p3":["model_profile_regression"],
  "R1.3.p1.m2":["model_profile_regression"],
  "R3.2.p1.m1":["model_profile_regression"],
  "R3.2.p1":["model_profile_regression"],
  "T1.p3.m2":["larva_observer_regression"],
  "T1.p3.m1":["larva_observer_regression"],
  "T1.p3":["larva_observer_regression"],
  "T1.p2.m1":["shadow_route_regression"],
  "T1.p2":["shadow_route_regression"],
  "T13.p1":["automation_draft_regression"],
  "T13.p1.m2":["automation_draft_regression"],
  "T2.p2":["capability_permissions_regression"],
  "T2.p2.m1":["capability_permissions_regression"],
  "T2.p2.m2":["capability_permissions_regression"],
  "R6.2.p1":["capability_permissions_regression"],
  "R6.2.p1.m1":["capability_permissions_regression"],
  "R6.2.p1.m2":["capability_permissions_regression"],
  "R6.2.p2.m1":["capability_permissions_regression"],
  "T13.p2.m1":["capability_permissions_regression"],
  "T3.p1":["coordinator_regression"],
  "T3.p1.m1":["coordinator_regression"],
  "T3.p1.m2":["coordinator_regression"],
  "T3.p2":["coordinator_regression"],
  "T3.p2.m1":["coordinator_regression"],
  "T4.p2":["runtime_state_regression"],
  "T4.p2.m1":["runtime_state_regression"],
  "T4.p2.m2":["runtime_state_regression"],
  "T5.p1":["runtime_state_regression"],
  "T5.p1.m1":["runtime_state_regression"],
  "T13.p2.m2":["runtime_state_regression"],
  "T5.p2":["component_protocol_regression"],
  "T5.p2.m1":["component_protocol_regression"],
  "T5.p2.m2":["component_protocol_regression"],
  "T6.p3":["context_packet_regression"],
  "T6.p3.m1":["context_packet_regression"],
  "T6.p3.m2":["context_packet_regression"],
  "T8.p2":["agent_bindings_regression"],
  "T8.p2.m1":["agent_bindings_regression"],
  "T8.p2.m2":["agent_bindings_regression"],
  "T10.p3.m1":["diagnostic_trace_regression"],
  "T5.p1.m2":["diagnostic_trace_regression"],
  "R6.1.p2":["auth_guard_regression"],
  "R6.1.p2.m1":["auth_guard_regression"],
  "R6.1.p2.m2":["auth_guard_regression"],
  "R6.1.p1":["tailscale_identity_regression"],
  "R6.1.p1.m1":["tailscale_identity_regression"],
  "B2.p1":["library_copy_regression"],
  "B2.p1.m1":["library_copy_regression"],
  "B2.p3":["library_edit_regression"],
  "B2.p3.m1":["library_edit_regression", "library_monitor_regression"],
  "B2.p3.m2":["library_edit_regression"],
  "B3.p4":["library_edit_regression"],
  "B3.p4.m2":["library_edit_regression"],
  "B2.p2":["library_search_regression"],
  "B2.p2.m1":["library_search_regression"],
  "B1.p1.m2":["file_preview_regression"],
  "C1c":["push_payload_regression"],
  "T2.p1":["tool_registry_regression"],
  "T2.p1.m1":["tool_registry_regression"],
  "T2.p1.m2":["tool_registry_regression"],
  "T8.p1":["tool_registry_regression"],
  "T8.p1.m1":["tool_registry_regression"],
  "T8.p1.m2":["tool_registry_regression"],
  "T11.p1":["health_registry_regression"],
  "T11.p1.m1":["health_registry_regression"],
  "T11.p1.m2":["health_registry_regression"],
  "T11.p2":["health_registry_regression"],
  "T11.p2.m1":["health_registry_regression"],
  "T11.p2.m2":["health_registry_regression"],

  "B1.p1":["files_browse_regression"],
  "B1.p1.m1":["files_browse_regression"],
  "B1.p2":["files_e2e", "files_lifecycle_regression", "files_access_regression"],
  "B3.p1":["word_document_regression"],
  "B3.p1.m1":["word_document_regression"],
  "B3.p1.m2":["word_document_regression"],
  "B3.p4.m1":["word_document_regression"],
  "C2.p2.m2":["gmail_e2e"],
  "D4.p2":["preventivi_e2e"],
  "D4.p2.m1":["preventivi_e2e"],
  "D4.p2.m2":["preventivi_e2e"],

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

/**
 * Atlas V3 semantic model. These records describe architecture and work; they
 * are not runtime health verdicts. The V2 node hierarchy remains authoritative.
 */
export type AtlasNodeKind = "star" | "planet" | "moon" | "area" | "branch" | "trunk" | "roots";
export type AtlasResponsibilityKind = "user_capability" | "internal_service" | "infrastructure" | "governance" | "unclassified";
export type AtlasIssueKind = "bug" | "integration" | "incomplete" | "missing_verification" | "improvement" | "architecture" | "unclassified";
export type AtlasIssueState = "open" | "in_progress" | "resolved" | "needs_verification";
export type AtlasEvidenceKind = "code_review" | "ci_test" | "debian_test" | "manual_observation" | "unknown";
export type AtlasRelationKind = "uses" | "depends_on" | "communicates_with" | "produces_for" | "verified_by" | "shares_evidence_with";
export type AtlasEvidence = {
  id:string;kind:AtlasEvidenceKind;nodeId:string;description:string;
  commit?:string;observedAt?:string;checkId?:string;scope?:string;result?:"pass"|"fail"|"unknown";
};
export type AtlasIssue = {
  id:string;ownerNodeId:string;title:string;kind:AtlasIssueKind;state:AtlasIssueState;
  severity?:"low"|"medium"|"high"|"critical"|"unknown";
  affectedNodeIds?:string[];evidenceIds?:string[];createdAt?:string;source?:"legacy"|"manual"|"code_review";
};
export type AtlasRelation = {
  from:string;to:string;kind:AtlasRelationKind;note?:string;
  status?:string;provenance?:string;
};
export type AtlasV3Overlay = {
  schemaVersion:3;
  nodeResponsibilities:Record<string,AtlasResponsibilityKind>;
  issues:AtlasIssue[];
  evidence:AtlasEvidence[];
  relations:AtlasRelation[];
};
/** Deterministic adapter: legacy knownIssues stay readable without double-counting. */
export function legacyIssues(nodes:Node[]):AtlasIssue[] {
  return nodes.flatMap(node=>(node.knownIssues||[]).map((title,index)=>({
    id:`legacy:${node.id}:${index+1}`,ownerNodeId:node.id,title,
    kind:"unclassified" as const,state:"open" as const,
    severity:"unknown" as const,source:"legacy" as const
  })));
}
/** A single owner is required; other affected nodes are references, not copies. */
export function validateAtlasOverlay(overlay:AtlasV3Overlay,nodes:Node[]):string[] {
  const ids=new Set(nodes.map(n=>n.id));
  const errors:string[]=[];
  const issueIds=new Set<string>();
  const evidenceIds=new Set<string>();
  if(overlay.schemaVersion!==3)errors.push("Unsupported Atlas schema version");
  for(const [id] of Object.entries(overlay.nodeResponsibilities))
    if(!ids.has(id))errors.push("Unknown responsibility node: "+id);
  for(const item of overlay.evidence){
    if(evidenceIds.has(item.id))errors.push("Duplicate evidence: "+item.id);
    evidenceIds.add(item.id);
    if(!ids.has(item.nodeId))errors.push("Unknown evidence node: "+item.nodeId);
  }
  for(const item of overlay.issues){
    if(issueIds.has(item.id))errors.push("Duplicate issue: "+item.id);
    issueIds.add(item.id);
    if(!ids.has(item.ownerNodeId))errors.push("Unknown issue owner: "+item.ownerNodeId);
    for(const id of item.affectedNodeIds||[])
      if(!ids.has(id))errors.push("Unknown affected node: "+id);
    for(const id of item.evidenceIds||[])
      if(!evidenceIds.has(id))errors.push("Unknown evidence: "+id);
  }
  const relationIds=new Set<string>();
  for(const relation of overlay.relations){
    if(!ids.has(relation.from)||!ids.has(relation.to))
      errors.push("Unknown relation endpoint: "+relation.from+" -> "+relation.to);
    if(relation.from===relation.to)errors.push("Self relation: "+relation.from);
    const key=[relation.from,relation.to,relation.kind].join("|");
    if(relationIds.has(key))errors.push("Duplicate relation: "+key);
    relationIds.add(key);
  }
  return errors;
}
