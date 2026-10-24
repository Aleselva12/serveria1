import projectStatus from "../project-status.generated.json";

/** Current goals from docs/project-status.json; historical 17 steps stay separate. */
export const missingConnections = {
  files: {
    label: "Sincronizzazione delle copie IA",
    detail: "Originali e copie IA: sincronizzazione rinviata all’upgrade hardware.",
    endpoints: "Versioni e conflitti da definire dopo l’upgrade",
  },
  agentFileTools: {
    label: "Accesso File Server e gestione avanzata Libreria",
    detail: "Accesso e modifiche agentiche ai file server, importazione, cartelle e restore rinviati all’upgrade hardware.",
    endpoints: "Contratti tool e radici autorizzate rinviati",
  },
  graphEdit: {
    label: "Esecuzione delle automazioni grafiche",
    detail: "Le bozze grafiche sono disponibili; esecuzione e pianificazione restano da implementare.",
    endpoints: "Validazione presente; esecuzione e pianificazione da definire",
  },
} as const;
export type ConnectionKey = keyof typeof missingConnections;

export const homeRoadmap = {
  ...projectStatus,
  categories: projectStatus.categories.map(category => ({
    ...category,
    goals: projectStatus.goals.filter(goal => goal.category === category.id),
  })),
};
