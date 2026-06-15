import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';
import type { MealPlan } from '../lib/types';
import LoadingSpinner from '../components/LoadingSpinner';

const PlansScreen: React.FC = () => {
  const [plans, setPlans] = useState<MealPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const { isPremium } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    supabase.from('meal_plans').select('*').order('month_number').then(({ data }) => {
      if (data) setPlans(data as MealPlan[]);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingSpinner message="Loading meal plans…" />;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>12-Month Meal Plans</h1>
        <p style={styles.sub}>Budget-optimized, compliance-verified</p>
      </div>
      <div style={styles.grid}>
        {plans.map(plan => {
          const locked = !isPremium && plan.month_number > 3;
          return (
            <div key={plan.id} onClick={() => !locked && navigate(`/plans/${plan.id}`)} style={{ ...styles.card, ...(locked ? styles.locked : {}) }}>
              <div style={styles.badge}>Month {plan.month_number}</div>
              <h3 style={styles.planTitle}>{plan.title}</h3>
              {plan.theme && <p style={styles.theme}>{plan.theme}</p>}
              {plan.kcal_target && <p style={styles.kcal}>{plan.kcal_target} kcal/day</p>}
              {locked && <div style={styles.lockBadge}>🔒 Premium</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { paddingBottom: 80, minHeight: '100vh', background: '#0d0d1a', color: '#fff' },
  header: { padding: '24px 20px 16px', background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)' },
  title: { margin: 0, fontSize: 24, fontWeight: 800 },
  sub: { margin: '4px 0 0', color: '#7ec8e3', fontSize: 13 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, padding: '16px 16px' },
  card: { background: '#1e1e3f', borderRadius: 12, padding: '16px 14px', cursor: 'pointer', position: 'relative', border: '1px solid #2e2e5e', transition: 'all 0.15s' },
  locked: { opacity: 0.55, cursor: 'default' },
  badge: { fontSize: 10, fontWeight: 700, color: '#4f8ef7', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 6 },
  planTitle: { margin: '0 0 4px', fontSize: 14, fontWeight: 700, lineHeight: 1.3 },
  theme: { margin: 0, fontSize: 11, color: '#aaa' },
  kcal: { margin: '4px 0 0', fontSize: 11, color: '#a0e0b0' },
  lockBadge: { position: 'absolute', top: 8, right: 8, background: '#333', borderRadius: 6, padding: '2px 6px', fontSize: 10, color: '#aaa' },
};

export default PlansScreen;
