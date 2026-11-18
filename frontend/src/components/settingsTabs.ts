/** Impostazioni sub-pages, addressed as #settings/<id>. */
export const SETTINGS_TABS = [
  { id: "generale", label: "Generale" },
  { id: "modelli", label: "Modelli IA" },
  { id: "memoria", label: "Memoria" },
  { id: "account", label: "Account collegati" },
  { id: "notifiche", label: "Notifiche" },
  { id: "permessi", label: "Accesso e permessi" },
  { id: "libreria", label: "Libreria IA" },
] as const;
export type SettingsTab = typeof SETTINGS_TABS[number]["id"];

export function isSettingsTab(value: string | undefined): value is SettingsTab {
  return SETTINGS_TABS.some(t => t.id === value);
}

/** Split a location hash into page and optional sub-page: "#settings/memoria" → ["settings", "memoria"]. */
export function splitHash(hash: string): [string, string | undefined] {
  const [page, sub] = hash.replace(/^#/, "").split("/", 2);
  return [page, sub];
}
