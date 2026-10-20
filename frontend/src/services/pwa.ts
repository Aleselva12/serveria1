export function registerPwa() {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js").catch(() => {
      // La UI deve restare utilizzabile anche se il browser non consente Service Worker.
    });
  });
}
