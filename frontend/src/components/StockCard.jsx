// A single live stock tile. Shows the ticker, company name, current price, and
// the per-tick change with up/down colour. A brief flash animation plays each
// time the price changes so updates are visually obvious.

import { useEffect, useRef, useState } from "react";

export default function StockCard({ ticker, name, data, onRemove }) {
  // `data` is the latest snapshot for this ticker (or undefined before first tick).
  const price = data?.price;
  const changePct = data?.change_pct ?? 0;
  const direction = data?.direction ?? "flat";

  // Flash effect: toggle a class whenever the price value changes.
  const [flash, setFlash] = useState("");
  const prevPrice = useRef(price);
  useEffect(() => {
    if (price === undefined || prevPrice.current === undefined) {
      prevPrice.current = price;
      return;
    }
    if (price > prevPrice.current) setFlash("flash-up");
    else if (price < prevPrice.current) setFlash("flash-down");
    prevPrice.current = price;
    const t = setTimeout(() => setFlash(""), 450);
    return () => clearTimeout(t);
  }, [price]);

  return (
    <div className={`stock-card ${flash}`}>
      <div className="stock-head">
        <div>
          <div className="stock-ticker">{ticker}</div>
          <div className="stock-name">{name}</div>
        </div>
        <button
          className="remove-btn"
          title={`Unsubscribe from ${ticker}`}
          onClick={() => onRemove(ticker)}
        >
          ×
        </button>
      </div>

      <div className="stock-price">
        {price === undefined ? "—" : `$${price.toFixed(2)}`}
      </div>

      <div className={`stock-change ${direction}`}>
        {direction === "up" ? "▲" : direction === "down" ? "▼" : "•"}{" "}
        {data ? `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%` : "waiting…"}
      </div>
    </div>
  );
}
