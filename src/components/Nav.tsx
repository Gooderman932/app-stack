import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Nav() {
  const { profile } = useAuth();
  return (
    <nav className="nav">
      <NavLink to="/plans" className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="ico">🍲</span>Plans
      </NavLink>
      <NavLink to="/shop" className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="ico">🏷️</span>Shop
      </NavLink>
      <NavLink to="/budget" className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="ico">📊</span>Budget
      </NavLink>
      {profile?.role === "producer" ? (
        <NavLink to="/producer" className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="ico">🌾</span>Sell
        </NavLink>
      ) : (
        <NavLink to="/producer-signup" className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="ico">🌾</span>Sell
        </NavLink>
      )}
      <NavLink to="/account" className={({ isActive }) => (isActive ? "active" : "")}>
        <span className="ico">👤</span>Account
      </NavLink>
    </nav>
  );
}
