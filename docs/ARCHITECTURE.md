# Architecture & Design

This document explains *how* the dashboard is built and *why* each decision was
made. It complements the top-level [README](../README.md), which covers usage.

---

## 1. The core problem the brief is testing

Stripped to its essence, the brief asks for **real-time, per-user, asynchronous
price updates**:

> "Update prices without refreshing" + "≥2 users … dashboards update
> asynchronously while both are open."

Everything else (login, subscribe) is scaffolding around that core. So the
architecture is organised around a clean answer to: *how does a price change on
the server reach exactly the right browsers, instantly, without a page reload?*

The answer here is a **server-push WebSocket** combined with a **per-connection
fan-out filter**.

---

## 2. Request/data flow

### 2.1 Authentication (email-verified registration + password login)

```
Browser                         Backend
  │  POST /auth/register {name,email,pw} │
  │ ───────────────────────────────────►│  hash_password() → PBKDF2 (salted)
  │                                      │  create user (verified = 0)
  │                                      │  otp.generate_and_send_otp()
  │                                      │   • secrets.randbelow → 6 digits
  │                                      │   • store HMAC-SHA256(code) + expiry
  │ ◄─────────────────────────────────── │  {message, dev_code?}
  │                                      │
  │  POST /auth/verify-email {email,code}│
  │ ───────────────────────────────────►│  otp.verify_otp() (constant-time)
  │                                      │   • burn code (single use)
  │                                      │  set verified = 1
  │ ◄─────────────────────────────────── │  {access_token: JWT}   (auto-login)
  │                                      │
  │  ── returning user ──                │
  │  POST /auth/login {email,password}   │
  │ ───────────────────────────────────►│  verify_password() (constant-time)
  │                                      │  reject if verified = 0
  │ ◄─────────────────────────────────── │  {access_token: JWT}
```

The OTP exists to **prove the user controls the email at registration time**:
an account stays `verified = 0` and cannot log in until the code is confirmed.
Passwords are PBKDF2-hashed; the JWT encodes `sub` (user id) and `email`, signed
HS256, and is stored in `localStorage` (see `auth.jsx`) so a refresh keeps the
session.

### 2.2 Subscription

```
Browser                         Backend
  │  POST /stocks/subscriptions {ticker} │
  │  Authorization: Bearer <JWT>         │
  │ ───────────────────────────────────►│  validate ticker ∈ catalogue
  │                                      │  DB: INSERT subscription
  │                                      │  manager.update_user_tickers(uid,set)
  │ ◄─────────────────────────────────── │  {tickers: [...]}
```

That last `update_user_tickers` call is the key link between REST and WebSocket:
adding a stock via REST instantly changes what the user's open socket receives.

### 2.3 Live prices (the heart)

```
        Price Engine (1 background task)
        every PRICE_TICK_SECONDS:
            _tick()  → random-walk all 5 prices
            broadcaster(snapshot)
                          │
                          ▼
        ConnectionManager.broadcast(snapshot)
            for each open Connection:
                filtered = snapshot ∩ connection.tickers
                websocket.send_json(filtered)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
   User A socket (GOOG)            User B socket (NVDA, META)
```

One engine, one tick loop, N sockets. Each socket gets a **different slice** of
the same snapshot — this is what makes the updates per-user and asynchronous.

---

## 3. Why these choices

### Why WebSocket (not polling)?
The brief says "without refreshing". Two ways to do that: short-polling (browser
asks every second) or server-push (server tells browser). Push via WebSocket is
the realistic broker-app approach — lower latency, less wasted traffic, and it
scales naturally to "many users updating asynchronously". FastAPI + uvicorn give
us first-class async WebSocket support.

### Why a single shared price engine?
Prices are a global truth (GOOG is GOOG for everyone). Generating them once per
tick and fanning out is far simpler and more consistent than per-user
generation. The *filtering* — not the *generation* — is per user.

### Why SQLite with raw `sqlite3` (no ORM)?
The data model is tiny (3 tables). Raw SQL keeps the persistence layer fully
visible and dependency-light, which suits a documented reference project and
avoids ORM/version friction on bleeding-edge Python.

### Why email-verified registration + password (not a toy login)?
The brief says "login using email". We implement a realistic account model:
register with a password, then **verify ownership of the email with an OTP**
before the account can be used. Passwords are PBKDF2-hashed; the OTP guards
sign-up. This is the registration-OTP flow the user explicitly asked for.

### Why JWT (not server sessions)?
Stateless: the same token authenticates both REST calls (Authorization header)
and the WebSocket handshake (query param), with no session store to maintain.

---

## 4. Concurrency & correctness

* The price engine runs as **one asyncio task** started in the FastAPI `lifespan`
  startup. It never blocks the event loop (`asyncio.sleep` between ticks), so
  HTTP and WebSocket handlers stay responsive.
* `ConnectionManager` guards its connection list with an `asyncio.Lock`. During a
  broadcast it copies the list under the lock, then sends outside the lock, so a
  slow client can't block others or deadlock against connect/disconnect.
* Sockets that error mid-send are reaped, so the list self-heals.
* OTP writes invalidate previous codes for the same email, so only the newest
  code is ever valid (prevents confusion + replay of old codes).

---

## 5. The data model

```sql
users(id, name, email UNIQUE, password_hash, verified, created_at)
                                                 -- password_hash = PBKDF2(salted)
                                                 -- verified flips to 1 after OTP
subscriptions(id, user_id → users.id, ticker, created_at,
              UNIQUE(user_id, ticker))           -- a user can't double-subscribe
otp_codes(id, email, code_hash, expires_at,
          attempts, consumed, created_at)        -- code_hash = HMAC-SHA256(code)
```

* `verified` gates login — an account is unusable until the registration OTP is
  confirmed.
* `UNIQUE(user_id, ticker)` makes subscribe **idempotent** at the DB level.
* `ON DELETE CASCADE` on subscriptions keeps things tidy if a user is removed.
* Only the **hash** of an OTP is stored, with `consumed`/`attempts` flags driving
  single-use + rate-limiting.

---

## 6. Frontend state model

* `auth.jsx` — React context holding `{token, email, name}`, persisted to
  localStorage. `App.jsx` renders `<Auth/>` when null, `<Dashboard/>` otherwise.
* `Auth.jsx` — one component with three modes (login / register / verify-email);
  registration flows into the OTP step, which auto-logs-in on success.
* `Dashboard.jsx` keeps three pieces of state:
  * `supported` — the catalogue (loaded once),
  * `subscribed` — the user's tickers (from REST, updated on add/remove),
  * `prices` — a `{ticker: {price, change_pct, direction}}` map, **merged** on
    every WebSocket message so a re-render only touches changed tiles.
* The WebSocket lifecycle lives in a `useEffect` keyed on the token, with
  **auto-reconnect** (1.5s) if the socket closes (e.g. backend restart).
* `StockCard.jsx` plays a brief green/red **flash** whenever its price changes,
  via a `useEffect` comparing the previous price.

---

## 7. What I'd add for production

| Concern | Production step |
|---|---|
| Transport security | Serve over HTTPS/WSS behind a reverse proxy. |
| Secrets | Strong random `JWT_SECRET` from a secrets manager. |
| Abuse | Per-email/IP rate limit on `request-otp`; CAPTCHA if needed. |
| Scale-out | Move price fan-out to Redis pub/sub so multiple API instances share one engine; move DB to Postgres. |
| Observability | Structured logging + metrics on tick latency and socket counts. |
| Tests | Add pytest for OTP/JWT/subscription logic and a WS integration test. |

---

## 8. File-to-responsibility index

| File | Responsibility |
|---|---|
| `app/main.py` | App creation, CORS, startup wiring (engine ↔ manager), routers. |
| `app/config.py` | Env-driven settings + tiny `.env` loader. |
| `app/catalogue.py` | The 5 supported stocks + seed prices. |
| `app/database.py` | SQLite schema + all queries (users/subs/otp). |
| `app/otp.py` | OTP generate, hash, deliver, verify. |
| `app/security.py` | JWT encode/decode + PBKDF2 password hash/verify. |
| `app/price_engine.py` | Random-walk generator + tick loop + snapshot shape. |
| `app/ws_manager.py` | Connection registry + per-user broadcast filter. |
| `app/deps.py` | `get_current_user` auth dependency. |
| `app/schemas.py` | Pydantic request/response models. |
| `app/routers/auth.py` | `/api/auth/*`. |
| `app/routers/stocks.py` | `/api/stocks/*`. |
| `app/routers/ws.py` | `/ws/prices` handshake + lifetime. |
