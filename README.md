# Stock Broker Client Web Dashboard

A real-time stock-broker client dashboard. Users **register an account with their
email** — verified by a **one-time passcode (OTP)** sent to that address — then
sign in with a password, subscribe to stocks by ticker code, and watch their
prices update **live, once per second, without ever refreshing the page**.
Multiple users can be signed in at once, each watching a different set of
stocks, and every dashboard updates **independently and asynchronously**.

> Prices are **simulated** with a server-side random-walk generator — no real
> market data feed is required (exactly as the brief allows).

---

## Table of contents

1. [What it does (maps to the brief)](#what-it-does-maps-to-the-brief)
2. [Tech stack](#tech-stack)
3. [How it works](#how-it-works)
4. [Project layout](#project-layout)
5. [Quick start](#quick-start)
6. [Using the app](#using-the-app)
7. [The OTP login system](#the-otp-login-system)
8. [Sending real emails](#sending-real-emails)
9. [API reference](#api-reference)
10. [Testing the requirements yourself](#testing-the-requirements-yourself)
11. [Configuration reference](#configuration-reference)
12. [Security notes](#security-notes)
13. [FAQ / troubleshooting](#faq--troubleshooting)

---

## What it does (maps to the brief)

| Brief requirement | How it's met |
|---|---|
| **0. Login using email** | **Register** with name + email + password → a 6-digit **OTP verifies the email** → account activated. Afterwards, **login = email + password**. |
| **1. Subscribe to a supported stock by ticker** | 5 supported tickers — **GOOG, TSLA, AMZN, META, NVDA**. Type the code (or click a chip) to add it to your watchlist. |
| **2. Update prices without refreshing** | A **WebSocket** pushes new prices to the browser every second; React re-renders the affected tiles in place. No reload. |
| **3. ≥2 users, different stocks, async updates** | Per-user watchlists stored in SQLite. The server fans out each tick to every open socket, filtered to *that* user's tickers, so two dashboards update at the same time, independently. |
| **Random prices, every second** | A background **price engine** moves each price once per second using **per-stock volatility, Gaussian moves, occasional shocks and gentle mean-reversion** — realistic rises and drops, not flat noise. |

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **Python + FastAPI** | Async-native (great for WebSockets), auto-generated API docs. |
| Real-time | **WebSocket** (native, via `uvicorn[standard]`) | True server push — the correct tool for "update without refresh". |
| Persistence | **SQLite** via stdlib `sqlite3` (no ORM) | Zero-setup, transparent, easy to read. |
| Auth | **Email-verified registration (OTP)** + **password login** + **JWT** (`PyJWT`) | Realistic signup with email confirmation; PBKDF2-hashed passwords; stateless sessions. |
| Frontend | **React + Vite** | Modern, fast dev server, component model fits live tiles. |

---

## How it works

```
                         ┌──────────────────────────────────────────┐
                         │              FastAPI backend             │
                         │                                          │
  Browser (User A)       │   ┌───────────────┐   once/sec           │
  ┌───────────────┐  WS  │   │ Price Engine  │──────────┐           │
  │ React         │◄─────┼───┤ (random walk) │          │           │
  │ Dashboard     │      │   └───────────────┘          ▼           │
  │  • GOOG tile  │      │                     ┌──────────────────┐ │
  └───────────────┘      │                     │ Connection       │ │
                         │   filtered to A ◄───┤ Manager (fan-out)│ │
  Browser (User B)       │                     │  per-user tickers│ │
  ┌───────────────┐  WS  │   filtered to B ◄───┤                  │ │
  │  • NVDA tile  │◄─────┼─────────────────────└──────────────────┘ │
  │  • META tile  │      │                                          │
  └───────────────┘      │   REST: /auth/* /stocks/*  ── SQLite     │
                         └──────────────────────────────────────────┘
```

* **Register**: `POST /api/auth/register` creates an unverified account and emails
  a code; `POST /api/auth/verify-email` confirms it, activates the account, and
  returns a **JWT** (auto-login). The browser stores the JWT (localStorage).
* **Login** (returning users): `POST /api/auth/login` with email + password
  returns a **JWT**.
* **Subscribe**: `POST /api/stocks/subscriptions` saves the ticker and tells the
  Connection Manager to start sending it to that user's open sockets.
* **Live prices**: the browser opens `WS /ws/prices?token=<JWT>`. Every second the
  Price Engine generates a fresh snapshot and the Connection Manager sends each
  socket only the tickers that socket's user subscribes to.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a deeper, file-by-file walkthrough.

---

## Project layout

```
stock-broker-dashboard/
├── README.md                      ← you are here
├── docs/
│   └── ARCHITECTURE.md            ← deep-dive design doc
├── backend/
│   ├── requirements.txt
│   ├── .env.example               ← copy to .env to customise
│   ├── run.sh                     ← one-command backend launcher (macOS/Linux)
│   ├── run.bat                    ← one-command backend launcher (Windows)
│   └── app/
│       ├── main.py                ← FastAPI app + startup wiring
│       ├── config.py              ← settings (env-driven)
│       ├── catalogue.py           ← the 5 supported stocks
│       ├── database.py            ← SQLite access (users, subs, otp)
│       ├── security.py            ← JWT create/verify
│       ├── otp.py                 ← OTP generate / send / verify
│       ├── price_engine.py        ← realistic price generator (vol + shocks)
│       ├── ws_manager.py          ← per-user WebSocket fan-out
│       ├── deps.py                ← "current user" auth dependency
│       ├── schemas.py             ← Pydantic request/response models
│       └── routers/
│           ├── auth.py            ← /api/auth/*
│           ├── stocks.py          ← /api/stocks/*
│           └── ws.py              ← /ws/prices
└── frontend/
    ├── package.json
    ├── vite.config.js             ← dev server + /api & /ws proxy
    └── src/
        ├── main.jsx
        ├── App.jsx                ← login vs dashboard switch
        ├── api.js                 ← REST + WS URL helpers
        ├── auth.jsx               ← JWT context (localStorage)
        ├── styles.css
        └── components/
            ├── Auth.jsx           ← register / verify-email / login screen
            ├── Dashboard.jsx      ← WebSocket + watchlist grid
            ├── StockCard.jsx      ← one live price tile
            └── SubscribeBox.jsx   ← add-by-ticker control
```

---

## Quick start

Works on **Linux, macOS and Windows**. You'll run two servers (backend + frontend)
in **two terminals**.

### Prerequisites

Install these first (any recent version is fine):

| Tool | Minimum | Check it's installed | Download |
|---|---|---|---|
| **Python** | 3.11+ | `python3 --version` (Windows: `python --version`) | <https://www.python.org/downloads/> |
| **Node.js** (incl. npm) | 18+ | `node --version` && `npm --version` | <https://nodejs.org/> |
| **Git** | any | `git --version` | <https://git-scm.com/downloads> |

> **Windows tip:** when installing Python, tick **“Add python.exe to PATH”**.

### 1) Get the code

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2) Backend — install dependencies & run (Terminal 1)

All commands run from the **`backend/`** folder. The steps below create an
isolated Python **virtual environment**, install the backend dependencies
(FastAPI, Uvicorn, PyJWT, email-validator — see `requirements.txt`), then start
the API server.

**Shortcut** — one command does all four steps for you:

| OS | Command (from `backend/`) |
|---|---|
| macOS / Linux | `./run.sh` |
| Windows | `.\run.bat` |

**Or do it step by step** (recommended if you want to see each stage):

<details open><summary><b>macOS / Linux</b></summary>

```bash
cd backend
python3 -m venv .venv                       # 1. create virtual environment
source .venv/bin/activate                   # 2. activate it
pip install -r requirements.txt             # 3. install dependencies
uvicorn app.main:app --reload --port 8000   # 4. run the API
```
</details>

<details><summary><b>Windows — PowerShell</b></summary>

```powershell
cd backend
python -m venv .venv                         # 1. create virtual environment
.venv\Scripts\Activate.ps1                   # 2. activate it
pip install -r requirements.txt             # 3. install dependencies
uvicorn app.main:app --reload --port 8000   # 4. run the API
```

> If PowerShell says *"running scripts is disabled on this system"*, run this
> once, then retry the activate step:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
</details>

<details><summary><b>Windows — Command Prompt (cmd)</b></summary>

```bat
cd backend
python -m venv .venv                         & rem 1. create virtual environment
.venv\Scripts\activate.bat                   & rem 2. activate it
pip install -r requirements.txt             & rem 3. install dependencies
uvicorn app.main:app --reload --port 8000   & rem 4. run the API
```
</details>

The backend is ready when it prints **`Application startup complete`**.
API docs live at <http://localhost:8000/docs>.

> **No database or `.env` setup needed.** A local SQLite file is created
> automatically on first run, and the app ships with sensible defaults (it runs
> in `DEV_MODE`, so no email account is required). See
> [Configuration reference](#configuration-reference) to customise.

### 3) Frontend — install dependencies & run (Terminal 2)

The same commands work on **every OS**. Run from the **`frontend/`** folder:

```bash
cd frontend
npm install        # installs React, Vite & other dependencies (first time only)
npm run dev        # starts the dashboard on http://localhost:5173
```

### 4) Open the app

Go to **<http://localhost:5173>**. Because the app runs in **DEV_MODE** by default,
your verification code is shown right on the screen (and printed in the backend
console), so you can register and sign in without any email setup.

### Running it again later (after first setup)

**Installation is one-time.** Once the virtual environment and `node_modules`
exist, you don't reinstall anything — just start the two servers:

| | macOS / Linux | Windows (PowerShell) |
|---|---|---|
| **Backend** (in `backend/`) | `source .venv/bin/activate`<br>`uvicorn app.main:app --reload --port 8000` | `.venv\Scripts\Activate.ps1`<br>`uvicorn app.main:app --reload --port 8000` |
| **Frontend** (in `frontend/`) | `npm run dev` | `npm run dev` |

> The `run.sh` / `run.bat` scripts are also safe to run every time — they create
> the venv only if it's missing and skip work that's already done — so you can
> just use those if you prefer one command.

> **Port already in use?** The app is resilient to this:
> - **Frontend (5173):** if it's taken, Vite automatically starts on the next
>   free port (5174, …) and prints the real URL — it still works, because the
>   frontend talks to the API through relative URLs, not a fixed port.
> - **Backend (8000):** set a different port with the `PORT` env var, e.g.
>   `PORT=8001 ./run.sh` (Windows: `set PORT=8001 && run.bat`). Then point the
>   frontend at it by copying `frontend/.env.example` to `frontend/.env` and
>   setting `VITE_API_TARGET=http://localhost:8001`.
>
> Or just free the port — macOS/Linux: `lsof -ti:8000 | xargs kill` ·
> Windows (PowerShell): `Get-NetTCPConnection -LocalPort 8000 | Select -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ }`.

---

## Using the app

1. **Create an account** — on the login screen click *Create an account*, enter a
   name, any email (e.g. `alice@example.com`) and a password (min 8 chars), then
   *Create account*.
2. **Verify your email** — a 6-digit code is emailed to you. In dev mode it's
   pre-filled and shown on screen. Click *Verify & continue* — you're now signed
   in. (Returning later? Just use *Sign in* with your email + password.)
3. **Add stocks** — type a ticker like `GOOG` and click *Add*, or click one of
   the supported-ticker chips.
4. **Watch them tick** — each tile updates every second, flashing green on an up
   move and red on a down move. The "Live" dot in the top bar confirms the
   WebSocket is connected.
5. **Remove a stock** — click the `×` on any tile.
6. **Try two users** — open a second browser (or an incognito window), register a
   *different* account, and subscribe to *different* stocks. Both dashboards
   update at the same time, each showing only its own stocks.

---

## The registration & OTP system

The OTP is the **email-verification gate for registration** — a genuine
one-time-passcode flow, not a fake:

1. You submit the signup form (name, email, password). The password is hashed
   with **PBKDF2-HMAC-SHA256** (200k iterations, per-user salt) — never stored in
   plaintext. The account is created **unverified** and cannot log in yet.
2. The server generates a **cryptographically random 6-digit code**
   (`secrets.randbelow`) and stores only an **HMAC-SHA256 hash** of it (keyed by
   the app secret) — the plaintext code is never persisted.
3. The code is **delivered by email** (or shown in the console in dev mode).
4. You enter the code → the server hashes your input and compares it in
   **constant time** (`hmac.compare_digest`). On success the account is marked
   **verified** and you're issued a **JWT** (auto-login).
5. The code **expires** after 5 minutes, is **single-use** (burned on success),
   and is invalidated after too many wrong attempts (anti-brute-force). You can
   *Resend code* if it lapses.
6. **Returning logins** use email + password (`/api/auth/login`) — the OTP isn't
   needed again. An unverified account that tries to log in is bounced back to
   the verify step with a fresh code.

---

## Sending real emails

By default the app prints OTP codes to the console (no email account needed).
To send **real** emails, edit `backend/.env`:

```ini
DEV_MODE=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_gmail_app_password   # a Google "App Password", not your login
SMTP_FROM=you@gmail.com
```

Restart the backend. Now codes are delivered to the user's inbox and are **never**
exposed in the API response.

> Gmail requires an [App Password](https://support.google.com/accounts/answer/185833)
> (with 2FA enabled). Any SMTP provider (SendGrid, Mailgun, your ISP) works too.

---

## API reference

Interactive docs (try every endpoint in the browser): **http://localhost:8000/docs**

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/register` | – | Create account `{name,email,password}`; emails an OTP. Returns `dev_code` in dev mode. |
| `POST` | `/api/auth/verify-email` | – | Verify the OTP `{email,code}` → activates account, returns JWT. |
| `POST` | `/api/auth/login` | – | `{email,password}` → returns JWT (verified accounts only). |
| `POST` | `/api/auth/resend-otp` | – | Re-send a verification code for an unverified account. |
| `GET`  | `/api/auth/me` | Bearer | Current user. |
| `GET`  | `/api/stocks/supported` | – | The 5 supported stocks. |
| `GET`  | `/api/stocks/subscriptions` | Bearer | My watchlist. |
| `POST` | `/api/stocks/subscriptions` | Bearer | Add `{ "ticker": "GOOG" }`. |
| `DELETE` | `/api/stocks/subscriptions/{ticker}` | Bearer | Remove a ticker. |
| `WS`   | `/ws/prices?token=<JWT>` | token | Live price stream (push every second). |
| `GET`  | `/api/health` | – | Liveness probe. |

---

## Testing the requirements yourself

**Live WebSocket stream (no refresh):** open the dashboard and watch the tiles —
the numbers change every second while the page never reloads.

**Two users, async, different stocks:** the included concurrency check (already
used during development) signs in two users, subscribes them to different
tickers, and prints what each socket receives:

```
alice -> [TSLA],  carol -> [NVDA, META]   (running concurrently)

alice  sees: TSLA=253.78
carol  sees: NVDA=124.84, META=525.97
carol  sees: NVDA=125.57, META=521.30
alice  sees: TSLA=255.07
```

Each user receives **only their own** stocks, at the same time → requirement #3. ✅

---

## Configuration reference

All settings live in `backend/.env` (copy from `.env.example`). Every value has a
default, so the app runs with no `.env` at all.

| Variable | Default | Meaning |
|---|---|---|
| `JWT_SECRET` | dev value | Signs JWTs **and** keys the OTP hash. Change in prod. |
| `JWT_EXPIRE_MINUTES` | `720` | Session lifetime. |
| `OTP_TTL_SECONDS` | `300` | How long a code is valid. |
| `DEV_MODE` | `true` | Show/return codes instead of requiring email. |
| `SMTP_*` | empty | SMTP server for real email delivery. |
| `CORS_ORIGINS` | localhost:5173 | Allowed frontend origins. |
| `PRICE_TICK_SECONDS` | `1` | Price update interval. |

---

## Security notes

* Passwords are **hashed with PBKDF2-HMAC-SHA256** (200k iterations, per-user
  salt) — never stored in plaintext.
* OTP codes are **hashed (HMAC-SHA256)**, never stored in plaintext.
* Codes **expire**, are **single-use**, and **rate-limited** by attempt count.
* Login uses a **generic error** for bad email vs. bad password (no account
  enumeration); resend-OTP responds uniformly for the same reason.
* Constant-time comparison avoids timing attacks.
* Sessions are **stateless JWTs**; the WebSocket handshake is authenticated.
* For production you would additionally: use HTTPS/WSS, set a strong random
  `JWT_SECRET`, add per-email request-OTP rate limiting, and move from SQLite to
  a managed database.

---

## FAQ / troubleshooting

**The dashboard says "Reconnecting…".** The backend isn't running or restarted —
the frontend auto-reconnects every 1.5s; start/await the backend.

**I didn't get an email.** In the default `DEV_MODE=true` the code is shown on
screen and in the backend console, not emailed. Set up SMTP (above) for real mail.

**"is not a supported ticker".** Only `GOOG, TSLA, AMZN, META, NVDA` are
supported, per the brief. Edit `backend/app/catalogue.py` to change the list.

**Prices reset when I restart the backend.** The price engine re-seeds from the
catalogue on startup; subscriptions and users persist in `backend/stockbroker.db`.
