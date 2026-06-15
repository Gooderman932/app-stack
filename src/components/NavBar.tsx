import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const tabs = [
  { path: '/', label: 'Plans', icon: '📅' },
  { path: '/shop', label: 'Shop', icon: '🛒' },
  { path: '/budget', label: 'Budget', icon: '💰' },
  { path: '/producers', label: 'Producers', icon: '🌾' },
  { path: '/account', label: 'Account', icon: '👤' },
];

const NavBar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <nav style={styles.nav}>
      {tabs.map(tab => {
        const active = location.pathname === tab.path || (tab.path !== '/' && location.pathname.startsWith(tab.path));
        return (
          <button key={tab.path} onClick={() => navigate(tab.path)} style={{ ...styles.tab, ...(active ? styles.active : {}) }}>
            <span style={styles.icon}>{tab.icon}</span>
            <span style={styles.label}>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
};

const styles: Record<string, React.CSSProperties> = {
  nav: { position: 'fixed', bottom: 0, left: 0, right: 0, background: '#1a1a2e', borderTop: '1px solid #2e2e5e', display: 'flex', paddingBottom: 'env(safe-area-inset-bottom)' },
  tab: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '8px 0', background: 'none', border: 'none', cursor: 'pointer', color: '#888', gap: 2 },
  active: { color: '#4f8ef7' },
  icon: { fontSize: 20 },
  label: { fontSize: 10, fontWeight: 600, letterSpacing: 0.3 },
};

export default NavBar;
