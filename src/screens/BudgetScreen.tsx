import React, { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';
import type { MealPlan } from '../lib/types';

interface BudgetEntry {
  month: number;
  title: string;
  estimatedCost: number;
  actualCost: number | null;
}

const BudgetScreen: React.FC = () => {
  const { session } = useAuth();
  const [entries, setEntries] = useState<BudgetEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const { data: plans } = await supabase.from('meal_plans').select('id, month_number, title').order('month_number');
      if (!plans) { setLoading(false); return; }

      const enriched: BudgetEntry[] = await Promise.all(
        (plans as Pick<MealPlan, 'id' | 'month_number' | 'title'>[]).map(async p => {
          const { data: slots } = await supabase.from('meal_slots').select('estimated_cost_usd').eq('meal_plan_id', p.id);
          const total = (slots ?? []).reduce((s: number, sl: { estimated_cost_usd: number | null }) => s + (sl.estimated_cost_usd ?? 0), 0);
          return { month: p.month_number, title: p.title, estimatedCost: total, actualCost: null };
        })
      );
      setEntries(enriched);
      setLoading(false);
    };
    load();
  }, []);

  const totalEstimated = entries.reduce((s, e) => s + e.estimatedCost, 0);
  const dailyAvg = entries.length > 0 ? (totalEstimated / (entries.length * 30)) : 0;

  if (loading) return <div style={{ color: '#fff', padding: 24 }}>Loading…</div>;
  if (!session) return <div style={{ color: '#fff', padding: 24 }}>Sign in to track your budget.</div>;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Budget Tracker</h1>
        <p style={styles.sub}>Full-year cost estimate</p>
      </div>

      <div style={styles.summaryRow}>
        <div style={styles.summaryCard}>
          <p style={styles.summaryLabel}>Annual Est.</p>
          <p style={styles.summaryVal}>${totalEstimated.toFixed(0)}</p>
        </div>
        <div style={styles.summaryCard}>
          <p style={styles.summaryLabel}>Daily Avg</p>
          <p style={styles.summaryVal}>${dailyAvg.toFixed(2)}</p>
        </div>
        <div style={styles.summaryCard}>
          <p style={styles.summaryLabel}>vs. SNAP Max</p>
          <p style={{ ...styles.summaryVal, color: dailyAvg < 6.2 ? '#a0e0b0' : '#ff6b6b' }}>
            {dailyAvg < 6.2 ? '✓ Under' : '↑ Over'}
          </p>
        </div>
      </div>

      <div style={styles.list}>
        {entries.map(e => (
          <div key={e.month} style={styles.row}>
            <div>
              <span style={styles.monthBadge}>Mo {e.month}</span>
              <span style={styles.rowTitle}>{e.title}</span>
            </div>
            <div style={styles.costs}>
              <span style={styles.est}>${e.estimatedCost.toFixed(2)}</span>
              <span style={styles.actual}>{e.actualCost !== null ? `$${e.actualCost.toFixed(2)}` : '—'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { paddingBottom: 80, background: '#0d0d1a', minHeight: '100vh', color: '#fff' },
  header: { padding: '24px 20px 16px', background: 'linear-gradient(135deg, #1a1a2e, #16213e)' },
  title: { margin: 0, fontSize: 24, fontWeight: 800 },
  sub: { margin: '4px 0 0', color: '#f7c74f', fontSize: 13 },
  summaryRow: { display: 'flex', gap: 10, padding: '16px 16px 8px' },
  summaryCard: { flex: 1, background: '#1e1e3f', borderRadius: 12, padding: '14px 12px', textAlign: 'center', border: '1px solid #2e2e5e' },
  summaryLabel: { margin: '0 0 4px', fontSize: 11, color: '#888', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 },
  summaryVal: { margin: 0, fontSize: 20, fontWeight: 800 },
  list: { padding: '8px 16px' },
  row: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: '#1e1e3f', borderRadius: 10, marginBottom: 8, border: '1px solid #2e2e5e' },
  monthBadge: { fontSize: 10, fontWeight: 700, color: '#4f8ef7', marginRight: 8, letterSpacing: 0.5 },
  rowTitle: { fontSize: 13, fontWeight: 600 },
  costs: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 },
  est: { fontSize: 14, fontWeight: 700, color: '#a0e0b0' },
  actual: { fontSize: 12, color: '#888' },
};

export default BudgetScreen;
