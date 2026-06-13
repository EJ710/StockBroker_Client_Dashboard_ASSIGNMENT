// Authentication context.
//
// Holds the logged-in user's JWT + email, persists them to localStorage so a
// refresh keeps you logged in, and exposes login()/logout() to the app.

import { createContext, useContext, useEffect, useState } from "react";

const AuthContext = createContext(null);

const STORAGE_KEY = "stockbroker.auth";

export function AuthProvider({ children }) {
  // Lazy-init from localStorage so a page refresh restores the session.
  const [auth, setAuth] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  // Keep localStorage in sync with the in-memory session.
  useEffect(() => {
    if (auth) localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    else localStorage.removeItem(STORAGE_KEY);
  }, [auth]);

  const login = (token, email, name) => setAuth({ token, email, name });
  const logout = () => setAuth(null);

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// Convenience hook so components can do: const { auth, login, logout } = useAuth();
export function useAuth() {
  return useContext(AuthContext);
}
