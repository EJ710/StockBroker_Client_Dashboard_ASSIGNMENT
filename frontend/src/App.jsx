// Top-level router: show the Dashboard when logged in, otherwise the Login.
import { useAuth } from "./auth.jsx";
import Auth from "./components/Auth.jsx";
import Dashboard from "./components/Dashboard.jsx";

export default function App() {
  const { auth } = useAuth();
  return auth ? <Dashboard /> : <Auth />;
}
