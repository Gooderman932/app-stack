import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Nav from "./components/Nav";
import Auth from "./screens/Auth";
import Plans from "./screens/Plans";
import PlanDetail from "./screens/PlanDetail";
import Shop from "./screens/Shop";
import Budget from "./screens/Budget";
import Producer from "./screens/Producer";
import ProducerSignup from "./screens/ProducerSignup";
import Account from "./screens/Account";

export default function App() {
  const { session, loading } = useAuth();

  if (loading) return <div className="spinner">Loading…</div>;

  if (!session) {
    return (
      <div className="app">
        <Auth />
      </div>
    );
  }

  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Navigate to="/plans" replace />} />
        <Route path="/plans" element={<Plans />} />
        <Route path="/plans/:id" element={<PlanDetail />} />
        <Route path="/shop" element={<Shop />} />
        <Route path="/budget" element={<Budget />} />
        <Route path="/producer" element={<Producer />} />
        <Route path="/producer-signup" element={<ProducerSignup />} />
        <Route path="/account" element={<Account />} />
        <Route path="*" element={<Navigate to="/plans" replace />} />
      </Routes>
      <Nav />
    </div>
  );
}
