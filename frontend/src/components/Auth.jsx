// Authentication screen with three modes:
//
//   "login"    — existing users sign in with email + password.
//   "register" — new users provide name + email + password; we email an OTP.
//   "verify"   — enter the OTP we emailed to activate the account (auto-login).
//
// The OTP step is the email-verification gate for REGISTRATION: a new account
// can't be used until the code is confirmed.

import { useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

export default function Auth() {
  const { login } = useAuth();

  const [mode, setMode] = useState("login"); // "login" | "register" | "verify"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  function resetMessages() {
    setError("");
    setInfo("");
  }

  // --- Register: create account + send OTP -> go to verify step ----------
  async function handleRegister(e) {
    e.preventDefault();
    resetMessages();
    setBusy(true);
    try {
      const res = await api.register(name.trim(), email.trim(), password);
      if (res.dev_code) {
        setDevCode(res.dev_code);
        setCode(res.dev_code); // pre-fill in dev mode
      }
      setMode("verify");
      setInfo(res.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // --- Verify: confirm OTP -> activate + auto login ----------------------
  async function handleVerify(e) {
    e.preventDefault();
    resetMessages();
    setBusy(true);
    try {
      const res = await api.verifyEmail(email.trim(), code.trim());
      login(res.access_token, res.email, res.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResend() {
    resetMessages();
    setBusy(true);
    try {
      const res = await api.resendOtp(email.trim());
      if (res.dev_code) {
        setDevCode(res.dev_code);
        setCode(res.dev_code);
      }
      setInfo(res.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // --- Login: email + password ------------------------------------------
  async function handleLogin(e) {
    e.preventDefault();
    resetMessages();
    setBusy(true);
    try {
      const res = await api.login(email.trim(), password);
      login(res.access_token, res.email, res.name);
    } catch (err) {
      // 403 => account exists but isn't verified: send them to verify.
      if (/not verified/i.test(err.message)) {
        setInfo("Your email isn't verified yet — we've sent you a fresh code.");
        await handleResend();
        setMode("verify");
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  const subtitle =
    mode === "login"
      ? "Sign in to your account."
      : mode === "register"
      ? "Create your account — we'll verify your email with a code."
      : `Enter the 6-digit code we sent to ${email}.`;

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-dot" /> StockBroker
        </div>
        <p className="auth-subtitle">{subtitle}</p>

        {/* ---------------- LOGIN ---------------- */}
        {mode === "login" && (
          <form onSubmit={handleLogin}>
            <label className="field-label" htmlFor="email">Email address</label>
            <input
              id="email" type="email" required autoFocus
              placeholder="you@example.com"
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
            <label className="field-label" htmlFor="password">Password</label>
            <input
              id="password" type="password" required
              placeholder="••••••••"
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
            <button className="btn-primary" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <p className="auth-switch">
              New here?{" "}
              <button type="button" className="link-inline"
                onClick={() => { resetMessages(); setMode("register"); }}>
                Create an account
              </button>
            </p>
          </form>
        )}

        {/* ---------------- REGISTER ---------------- */}
        {mode === "register" && (
          <form onSubmit={handleRegister}>
            <label className="field-label" htmlFor="name">Full name</label>
            <input
              id="name" type="text" required autoFocus
              placeholder="Alice Smith"
              value={name} onChange={(e) => setName(e.target.value)}
            />
            <label className="field-label" htmlFor="email">Email address</label>
            <input
              id="email" type="email" required
              placeholder="you@example.com"
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
            <label className="field-label" htmlFor="password">
              Password <span className="hint">(min 8 characters)</span>
            </label>
            <input
              id="password" type="password" required minLength={8}
              placeholder="Choose a password"
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
            <button className="btn-primary" disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
            </button>
            <p className="auth-switch">
              Already have an account?{" "}
              <button type="button" className="link-inline"
                onClick={() => { resetMessages(); setMode("login"); }}>
                Sign in
              </button>
            </p>
          </form>
        )}

        {/* ---------------- VERIFY ---------------- */}
        {mode === "verify" && (
          <form onSubmit={handleVerify}>
            {devCode && (
              <div className="dev-hint">
                Dev mode — your code is <strong>{devCode}</strong>
              </div>
            )}
            <label className="field-label" htmlFor="code">Verification code</label>
            <input
              id="code" inputMode="numeric" maxLength={6} required autoFocus
              placeholder="123456" className="otp-input"
              value={code} onChange={(e) => setCode(e.target.value)}
            />
            <button className="btn-primary" disabled={busy}>
              {busy ? "Verifying…" : "Verify & continue"}
            </button>
            <button type="button" className="btn-link" onClick={handleResend}
              disabled={busy}>
              Resend code
            </button>
            <button type="button" className="btn-link"
              onClick={() => { resetMessages(); setMode("login"); setCode(""); setDevCode(null); }}>
              ← Back to sign in
            </button>
          </form>
        )}

        {info && <div className="info-msg">{info}</div>}
        {error && <div className="error-msg">{error}</div>}
      </div>
    </div>
  );
}
