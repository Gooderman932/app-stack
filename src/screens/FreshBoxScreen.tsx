import React, { useEffect, useState } from 'react';
import { Browser } from '@capacitor/browser';
import { supabase } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';
import type { FreshBoxSubscription } from '../lib/types';

const FRESH_BOX_CHECKOUT = 'https://budgetmealplatform.com/fresh-box-checkout';

const PLANS = [
  { size: 'small' as const, label: 'Small Box', servings: '2 people · ~$28/wk', price: 28 },
  { size: 'medium' as const, label: 'Medium Box', servings: '4 people · ~$49/wk', price: 49 },
  { size: 'large' as const, label: 'Large Box', servings: '6 people · ~$68/wk', price: 68 },
];

const FreshBoxScreen: React.FC = () => {
  const { session, isKansas, profile } = useAuth();
  const [existing, setExisting] = useState<FreshBoxSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSize, setSelectedSize] = useState<'small' | 'medium' | 'large'>('medium');
  const [frequency, setFrequency] = useState<'weekly' | 'biweekly'>('weekly');

  useEffect(() => {
    if (!session) { setLoading(false); return; }
    supabase
      .from('fresh_box_subscriptions')
      .select('*')
      .eq('user_id', session.user.id)
      .maybeSingle()
      .then(({ data }) => {
        setExisting(data as FreshBoxSubscription | null);
        setLoading(false);
      });
  }, [session]);

  // Not in Kansas — show waitlist
  if (!isKansas) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h1 style={styles.title}>Fresh Box</h1>
          <p style={styles.sub}>Local fresh ingredients, weekly delivered</p>
        </div>
        <div style={styles.waitlistCard}>
          <div style={styles.waitlistIcon}>📍</div>
          <h2 style={styles.waitlistTitle}>Coming to Your Area</h2>
          <p style={styles.waitlistBody}>
            Fresh Box deliveries are currently available in Kansas only, sourced directly
            from our Kansas Producer Network. We're expanding soon — join the waitlist to
            get notified when we launch in your zip code.
          </p>
          <button
            style={styles.waitlistBtn}
            onClick={() => Browser.open({ url: 'https://budgetmealplatform.com/waitlist' })}
          >
            Join Waitlist
          </button>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div style={styles.container}>
        <div style={styles.header}><h1 style={styles.title}>Fresh Box</h1></div>
        <p style={{ color: '#aaa', padding: 24 }}>Sign in to subscribe to Fresh Box deliveries.</p>
      </div>
    );
  }

  if (loading) return <div style={{ color: '#fff', padding: 24 }}>Loading…</div>;

  if (existing && existing.status === 'active') {
    return (
      <div style={styles.container}>
        <div style={styles.header}><h1 style={styles.title}>Fresh Box</h1></div>
        <div style={styles.activeCard}>
          <p style={styles.activeLabel}>Active Subscription</p>
          <p style={styles.activeSize}>{existing.plan_size.charAt(0).toUpperCase() + existing.plan_size.slice(1)} Box · {existing.frequency}</p>
          <p style={styles.activePrice}>${existing.price_usd}/delivery</p>
          {existing.next_delivery_date && (
            <p style={styles.activeNext}>Next delivery: {new Date(existing.next_delivery_date).toLocaleDateString()}</p>
          )}
          <button
            style={styles.manageBtn}
            onClick={() => Browser.open({ url: 'https://budgetmealplatform.com/manage-subscription' })}
          >
            Manage Subscription
          </button>
        </div>
      </div>
    );
  }

  const chosen = PLANS.find(p => p.size === selectedSize)!;
  const price = frequency === 'biweekly' ? (chosen.price * 0.9).toFixed(2) : chosen.price.toFixed(2);

  const handleSubscribe = async () => {
    const params = new URLSearchParams({
      size: selectedSize,
      frequency,
      zip: profile?.zip_code ?? '',
      email: profile?.email ?? '',
    });
    await Browser.open({ url: `${FRESH_BOX_CHECKOUT}?${params}` });
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Fresh Box</h1>
        <p style={styles.sub}>Kansas-grown · Direct from our producer network</p>
      </div>

      <div style={styles.content}>
        <p style={styles.intro}>
          Weekly or biweekly delivery of fresh, locally-sourced ingredients matched to your
          active meal plan — picked and packed by Kansas producers in our network.
        </p>

        <h3 style={styles.sectionHead}>Choose Your Box</h3>
        {PLANS.map(plan => (
          <button
            key={plan.size}
            style={{ ...styles.planCard, ...(selectedSize === plan.size ? styles.planSelected : {}) }}
            onClick={() => setSelectedSize(plan.size)}
          >
            <div>
              <p style={styles.planName}>{plan.label}</p>
              <p style={styles.planServings}>{plan.servings}</p>
            </div>
            {selectedSize === plan.size && <span style={styles.checkmark}>✓</span>}
          </button>
        ))}

        <h3 style={styles.sectionHead}>Frequency</h3>
        <div style={styles.freqRow}>
          <button
            style={{ ...styles.freqBtn, ...(frequency === 'weekly' ? styles.freqActive : {}) }}
            onClick={() => setFrequency('weekly')}
          >
            Weekly
          </button>
          <button
            style={{ ...styles.freqBtn, ...(frequency === 'biweekly' ? styles.freqActive : {}) }}
            onClick={() => setFrequency('biweekly')}
          >
            Biweekly <span style={{ fontSize: 10, color: '#a0e0b0' }}>Save 10%</span>
          </button>
        </div>

        <div style={styles.summary}>
          <p style={styles.summaryText}>{chosen.label} · {frequency}</p>
          <p style={styles.summaryPrice}>${price} per delivery</p>
        </div>

        <button onClick={handleSubscribe} style={styles.subscribeBtn}>
          Subscribe Now →
        </button>
        <p style={styles.disclaimer}>
          Pause or cancel anytime. Deliveries to Kansas addresses only.
          Fresh box uses the Regional Fresh pipeline per KDA regulations.
        </p>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { paddingBottom: 80, background: '#0d0d1a', minHeight: '100vh', color: '#fff' },
  header: { padding: '24px 20px 16px', background: 'linear-gradient(135deg, #1a2a1a, #162e16)' },
  title: { margin: 0, fontSize: 24, fontWeight: 800 },
  sub: { margin: '4px 0 0', color: '#a0e0b0', fontSize: 13 },
  waitlistCard: { margin: '24px 16px', background: '#1e1e3f', borderRadius: 16, padding: '28px 20px', textAlign: 'center', border: '1px solid #2e2e5e' },
  waitlistIcon: { fontSize: 40, marginBottom: 12 },
  waitlistTitle: { margin: '0 0 12px', fontSize: 20, fontWeight: 700 },
  waitlistBody: { color: '#bbb', fontSize: 14, lineHeight: 1.7, margin: '0 0 20px' },
  waitlistBtn: { padding: '13px 32px', background: '#a0e0b0', border: 'none', borderRadius: 10, color: '#0d0d1a', fontWeight: 700, fontSize: 15, cursor: 'pointer' },
  activeCard: { margin: '16px 16px', background: '#1a2a1a', borderRadius: 14, padding: '20px', border: '1px solid #2a4a2a' },
  activeLabel: { margin: '0 0 4px', fontSize: 11, fontWeight: 700, color: '#a0e0b0', letterSpacing: 1, textTransform: 'uppercase' as const },
  activeSize: { margin: '0 0 4px', fontSize: 18, fontWeight: 700 },
  activePrice: { margin: '0 0 4px', fontSize: 14, color: '#a0e0b0' },
  activeNext: { margin: '0 0 16px', fontSize: 13, color: '#888' },
  manageBtn: { padding: '12px 24px', background: '#a0e0b0', border: 'none', borderRadius: 10, color: '#0d0d1a', fontWeight: 700, cursor: 'pointer' },
  content: { padding: '16px' },
  intro: { fontSize: 14, color: '#bbb', lineHeight: 1.6, marginBottom: 20 },
  sectionHead: { fontSize: 12, fontWeight: 700, color: '#a0e0b0', textTransform: 'uppercase' as const, letterSpacing: 0.8, margin: '20px 0 10px' },
  planCard: { width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#1e1e3f', border: '1px solid #2e2e5e', borderRadius: 12, padding: '14px 16px', marginBottom: 8, cursor: 'pointer', color: '#fff', textAlign: 'left' as const, boxSizing: 'border-box' as const },
  planSelected: { border: '2px solid #a0e0b0', background: '#1a2a1a' },
  planName: { margin: 0, fontSize: 15, fontWeight: 700 },
  planServings: { margin: '2px 0 0', fontSize: 12, color: '#888' },
  checkmark: { color: '#a0e0b0', fontSize: 18, fontWeight: 700 },
  freqRow: { display: 'flex', gap: 10, marginBottom: 20 },
  freqBtn: { flex: 1, padding: '12px 0', background: '#1e1e3f', border: '1px solid #2e2e5e', borderRadius: 10, color: '#aaa', fontWeight: 600, cursor: 'pointer', fontSize: 14, display: 'flex', flexDirection: 'column' as const, alignItems: 'center', gap: 2 },
  freqActive: { background: '#1a2a1a', border: '2px solid #a0e0b0', color: '#fff' },
  summary: { background: '#1a2a1a', borderRadius: 12, padding: '14px 16px', marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: '1px solid #2a4a2a' },
  summaryText: { margin: 0, fontSize: 14, color: '#ccc' },
  summaryPrice: { margin: 0, fontSize: 20, fontWeight: 800, color: '#a0e0b0' },
  subscribeBtn: { width: '100%', padding: '15px 0', background: '#a0e0b0', border: 'none', borderRadius: 12, color: '#0d0d1a', fontWeight: 800, fontSize: 16, cursor: 'pointer', marginBottom: 12 },
  disclaimer: { fontSize: 11, color: '#555', textAlign: 'center' as const, lineHeight: 1.5 },
};

export default FreshBoxScreen;
