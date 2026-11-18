/** Sistema sub-pages, addressed as #system/<id>. Old page ids still open the matching tab. */
export const SYSTEM_TABS = [
  { id: "salute", label: "Salute" },
  { id: "aggiornamenti", label: "Aggiornamenti" },
  { id: "macchine", label: "Macchine" },
  { id: "attivita", label: "Attività tecnica" },
] as const;
export type SystemTab = typeof SYSTEM_TABS[number]["id"];

export function isSystemTab(value: string | undefined): value is SystemTab {
  return SYSTEM_TABS.some(t => t.id === value);
}

/** Pages that used to stand alone and now live inside Sistema. */
export const LEGACY_SYSTEM_PAGES: Record<string, SystemTab> = {
  updates: "aggiornamenti",
  machines: "macchine",
  activity: "attivita",
};

/** Resolve a hash page/sub pair to a Sistema tab, or null when it is not a Sistema address. */
export function systemTabFor(page: string, sub: string | undefined): SystemTab | null {
  if (page === "system") return isSystemTab(sub) ? sub : "salute";
  return LEGACY_SYSTEM_PAGES[page] ?? null;
}
