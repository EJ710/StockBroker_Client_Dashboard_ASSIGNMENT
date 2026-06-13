// Controls for adding a stock to the watchlist by ticker code.
//
// Offers both a free-text input (type "GOOG" and Add, as the brief specifies)
// and quick-add chips for any supported tickers not yet subscribed.

import { useState } from "react";

export default function SubscribeBox({ supported, subscribed, onAdd, error }) {
  const [ticker, setTicker] = useState("");

  const notYetSubscribed = supported.filter(
    (s) => !subscribed.includes(s.ticker)
  );

  function submit(e) {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (t) onAdd(t);
    setTicker("");
  }

  return (
    <div className="subscribe-box">
      <form onSubmit={submit} className="subscribe-form">
        <input
          placeholder="Enter ticker (e.g. GOOG)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          maxLength={6}
        />
        <button className="btn-primary small">Add</button>
      </form>

      {error && <div className="error-msg inline">{error}</div>}

      {notYetSubscribed.length > 0 && (
        <div className="chips">
          <span className="chips-label">Supported:</span>
          {notYetSubscribed.map((s) => (
            <button
              key={s.ticker}
              className="chip"
              title={s.name}
              onClick={() => onAdd(s.ticker)}
            >
              + {s.ticker}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
