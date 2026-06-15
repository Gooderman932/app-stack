import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import NavBar from './components/NavBar';
import PlansScreen from './screens/PlansScreen';
import PlanDetailScreen from './screens/PlanDetailScreen';
import ShopScreen from './screens/ShopScreen';
import BudgetScreen from './screens/BudgetScreen';
import ProducersScreen from './screens/ProducersScreen';
import AccountScreen from './screens/AccountScreen';
import FreshBoxScreen from './screens/FreshBoxScreen';

const App: React.FC = () => (
  <BrowserRouter>
    <AuthProvider>
      <CartProvider>
        <div style={{ fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif", background: '#0d0d1a', minHeight: '100vh' }}>
          <Routes>
            <Route path="/" element={<PlansScreen />} />
            <Route path="/plans/:id" element={<PlanDetailScreen />} />
            <Route path="/shop" element={<ShopScreen />} />
            <Route path="/budget" element={<BudgetScreen />} />
            <Route path="/producers" element={<ProducersScreen />} />
            <Route path="/account" element={<AccountScreen />} />
            <Route path="/fresh-box" element={<FreshBoxScreen />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <NavBar />
        </div>
      </CartProvider>
    </AuthProvider>
  </BrowserRouter>
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
