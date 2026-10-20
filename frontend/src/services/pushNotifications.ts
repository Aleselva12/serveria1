import { authenticatedFetch } from "./transport";
import { apiBaseUrl } from "./api";

function decodeKey(value: string): ArrayBuffer {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const raw = atob((value + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (char) => char.charCodeAt(0)).buffer;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authenticatedFetch(apiBaseUrl + "/api/v1/notifications" + path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : "Notifiche non disponibili.");
  }
  return body as T;
}

export type PushState = {
  supported: boolean;
  permission: NotificationPermission | "unsupported";
  subscribed: boolean;
  endpoint?: string;
};

export async function currentPushState(): Promise<PushState> {
  if (
    typeof window === "undefined" ||
    !window.isSecureContext ||
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    typeof Notification === "undefined"
  ) {
    return { supported: false, permission: "unsupported", subscribed: false };
  }
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  return {
    supported: true,
    permission: Notification.permission,
    subscribed: Boolean(subscription),
    endpoint: subscription?.endpoint,
  };
}

export async function enablePushNotifications(label = "iPhone"): Promise<PushState> {
  const state = await currentPushState();
  if (!state.supported) {
    throw new Error("Web Push richiede la PWA installata e una connessione HTTPS.");
  }
  const permission = Notification.permission === "granted"
    ? "granted"
    : await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(permission === "denied" ? "Notifiche bloccate su questo dispositivo." : "Permesso notifiche non concesso.");
  }
  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    const config = await request<{supported:boolean; publicKey:string|null}>("/config");
    if (!config.supported || !config.publicKey) {
      throw new Error("Il server non riesce a preparare le chiavi Web Push.");
    }
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: decodeKey(config.publicKey),
    });
  }
  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
    throw new Error("Subscription push incompleta.");
  }
  await request("/subscriptions", {
    method: "POST",
    body: JSON.stringify({
      endpoint: json.endpoint,
      p256dh: json.keys.p256dh,
      auth: json.keys.auth,
      label,
      user_agent: navigator.userAgent,
    }),
  });
  return currentPushState();
}

export async function disablePushNotifications(): Promise<PushState> {
  const state = await currentPushState();
  if (!state.supported) return state;
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    await request("/subscriptions", {
      method: "DELETE",
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    });
    await subscription.unsubscribe();
  }
  return currentPushState();
}

export async function sendTestPush(): Promise<void> {
  const state = await currentPushState();
  if (!state.subscribed || !state.endpoint) {
    throw new Error("Attiva prima le notifiche su questo dispositivo.");
  }
  await request("/test", {
    method: "POST",
    body: JSON.stringify({ endpoint: state.endpoint }),
  });
}
