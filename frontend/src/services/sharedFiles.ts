// Keep private tokens in the fragment and accept only our two download routes.
export function sharePageUrl(apiPath: string, origin: string): string {
  const match = /^\/api\/v1\/(server|library)\/files\/shared\/([A-Za-z0-9_-]{20,100})$/.exec(apiPath);
  if (!match) throw new Error("Collegamento condiviso non valido.");
  return new URL(`/#/shared/${match[1]}/${match[2]}`, origin).href;
}

export function sharedDownloadPath(fragment: string): string | null {
  const match = /^#\/shared\/(server|library)\/([A-Za-z0-9_-]{20,100})$/.exec(fragment);
  return match ? `/api/v1/${match[1]}/files/shared/${match[2]}` : null;
}
