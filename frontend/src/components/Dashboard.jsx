// The main dashboard.
//
// Responsibilities:
//   * Load the supported-stock catalogue + this user's subscriptions (REST).
//   * Open the live-price WebSocket and keep a `prices` map updated in state,
//     re-rendering on every tick WITHOUT a page refresh (requirement #2).
//   * Subscribe / unsubscribe to tickers; the backend pushes the new set to the
//     socket so the grid updates immediately.
//   * Show a live connection indicator and auto-reconnect if the socket drops.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, priceSocketUrl } from "../api.js";
import { useAuth } from "../auth.jsx";
import StockCard from "./StockCard.jsx";
import SubscribeBox from "./SubscribeBox.jsx";

export default function Dashboard() {
  const { auth, logout } = useAuth();
  const { token, email } = auth;

  const [supported, setSupported] = useState([]);
  const [subscribed, setSubscribed] = useState([]);
  const [prices, setPrices] = useState({}); // { GOOG: {price, change_pct, ...} }
  const [connected, setConnected] = useState(false);
  const [subError, setSubError] = useState("");

  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  // --- Initial data load -------------------------------------------------
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [sup, subs] = await Promise.all([
          api.supported(token),
          api.subscriptions(token),
        ]);
        if (!alive) return;
        setSupported(sup);
        setSubscribed(subs.tickers);
      } catch {
        // A failed load almost always means an expired token — log out.
        logout();
      }
    })();
    return () => {
      alive = false;
    };
  }, [token, logout]);

  // --- WebSocket lifecycle ----------------------------------------------
  const connect = useCallback(() => {
    const ws = new WebSocket(priceSocketUrl(token));
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.type === "prices") {
        // Merge so we keep showing a stock while a fresh tick arrives.
        setPrices((prev) => ({ ...prev, ...msg.prices }));
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect after a short delay (e.g. server restart).
      reconnectRef.current = setTimeout(connect, 1500);
    };

    ws.onerror = () => ws.close();
  }, [token]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  // --- Subscribe / unsubscribe ------------------------------------------
  async function handleAdd(ticker) {
    setSubError("");
    try {
      const res = await api.subscribe(token, ticker);
      setSubscribed(res.tickers);
    } catch (err) {
      setSubError(err.message);
    }
  }

  async function handleRemove(ticker) {
    setSubError("");
    try {
      const res = await api.unsubscribe(token, ticker);
      setSubscribed(res.tickers);
      // Drop its price tile immediately.
      setPrices((prev) => {
        const next = { ...prev };
        delete next[ticker];
        return next;
      });
    } catch (err) {
      setSubError(err.message);
    }
  }

  const nameFor = (ticker) =>
    supported.find((s) => s.ticker === ticker)?.name || "";

  return (
    <div className="dashboard">
      <header className="topbar">
        <div className="brand">
          <span className="brand-dot" /> StockBroker
        </div>
        <div className="topbar-right">
          <span className={`conn ${connected ? "live" : "down"}`}>
            <span className="conn-dot" />
            {connected ? "Live" : "Reconnecting…"}
          </span>
          <span className="user-email">{email}</span>
          <button className="btn-link" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <h2>Add a stock to your watchlist</h2>
          <SubscribeBox
            supported={supported}
            subscribed={subscribed}
            onAdd={handleAdd}
            error={subError}
          />
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Your watchlist</h2>
            <span className="muted">
              {subscribed.length} stock{subscribed.length === 1 ? "" : "s"} ·
              updates every second
            </span>
          </div>

          {subscribed.length === 0 ? (
            <div className="empty">
              You're not watching any stocks yet. Add one above to see live
              prices.
            </div>
          ) : (
            <div className="grid">
              {subscribed.map((ticker) => (
                <StockCard
                  key={ticker}
                  ticker={ticker}
                  name={nameFor(ticker)}
                  data={prices[ticker]}
                  onRemove={handleRemove}
                />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
