export async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase())) headers.set("X-Cora-Client", "ui");
  const response = await fetch(input, { ...init, headers, credentials: "include" });
  if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event("cora:unauthorized"));
  return response;
}
