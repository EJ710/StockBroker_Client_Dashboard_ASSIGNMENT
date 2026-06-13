// Thin wrapper around the backend REST API.
//
// All paths are relative ("/api/...") and proxied to the FastAPI server by Vite
// in development (see vite.config.js). The JWT, when present, is attached as a
// Bearer token automatically.

const BASE = ""; // same-origin; Vite proxies /api -> :8000

async function request(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // Try to parse JSON either way so we can surface the API's error detail.
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  // --- auth ---
  register: (name, email, password) =>
    request("/api/auth/register", {
      method: "POST",
      body: { name, email, password },
    }),
  verifyEmail: (email, code) =>
    request("/api/auth/verify-email", { method: "POST", body: { email, code } }),
  login: (email, password) =>
    request("/api/auth/login", { method: "POST", body: { email, password } }),
  resendOtp: (email) =>
    request("/api/auth/resend-otp", { method: "POST", body: { email } }),
  me: (token) => request("/api/auth/me", { token }),

  // --- stocks ---
  supported: (token) => request("/api/stocks/supported", { token }),
  subscriptions: (token) => request("/api/stocks/subscriptions", { token }),
  subscribe: (token, ticker) =>
    request("/api/stocks/subscriptions", {
      method: "POST",
      token,
      body: { ticker },
    }),
  unsubscribe: (token, ticker) =>
    request(`/api/stocks/subscriptions/${ticker}`, { method: "DELETE", token }),
};

// Build the WebSocket URL for the live price stream, carrying the JWT as a
// query param (browsers can't set headers on a WS handshake).
export function priceSocketUrl(token) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/prices?token=${encodeURIComponent(
    token
  )}`;
}
