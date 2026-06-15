import React, { useState } from 'react';
import { Purchases } from '@revenuecat/purchases-capacitor';
import { BILLING } from '../lib/billingConfig';

interface Props {
  feature: string;
  onClose?: () => void;
}

const Paywall: React.FC<Props> = ({ feature, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePurchase = async () => {
    setLoading(true);
    setError(null);
    try {
      const offerings = await Purchases.getOfferings();
      const pkg = offerings.current?.availablePackages.find(
        p => p.identifier === BILLING.PRODUCT_ID
      ) ?? offerings.current?.availablePackages[0];
      if (!pkg) throw new Error('No subscription package found.');
      await Purchases.purchasePackage({ aPackage: pkg });
      onClose?.();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Purchase cancelled.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.card}>
        <h2 style={styles.title}>Premium Feature</h2>
        <p style={styles.body}>
          <strong>{feature}</strong> is available on the Premium plan.
        </p>
        <ul style={styles.list}>
          <li>✓ Portion scaling for any household size</li>
          <li>✓ Batch-prep Sunday cook plans</li>
          <li>✓ Allergy swap recommendations</li>
          <li>✓ Local grocery price sync</li>
          <li>✓ Full 12-month personalized library</li>
        </ul>
        <p style={styles.price}>$9.99 / month — cancel anytime</p>
        {error && <p style={styles.error}>{error}</p>}
        <button onClick={handlePurchase} disabled={loading} style={styles.btn}>
          {loading ? 'Loading…' : 'Start Premium'}
        </button>
        {onClose && (
          <button onClick={onClose} style={styles.secondary}>
            Maybe later
          </button>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999 },
  card: { background: '#1e1e3f', borderRadius: 16, padding: '28px 24px', maxWidth: 380, width: '90%', color: '#fff' },
  title: { margin: '0 0 8px', fontSize: 22, fontWeight: 700 },
  body: { margin: '0 0 16px', color: '#ccc', fontSize: 15 },
  list: { padding: '0 0 0 4px', listStyle: 'none', margin: '0 0 20px', color: '#a0e0b0', lineHeight: 2, fontSize: 14 },
  price: { fontWeight: 700, fontSize: 18, marginBottom: 16, color: '#7ec8e3' },
  error: { color: '#ff6b6b', fontSize: 13, marginBottom: 12 },
  btn: { width: '100%', padding: '14px 0', background: '#4f8ef7', border: 'none', borderRadius: 10, color: '#fff', fontWeight: 700, fontSize: 16, cursor: 'pointer', marginBottom: 10 },
  secondary: { width: '100%', padding: '10px 0', background: 'transparent', border: '1px solid #555', borderRadius: 10, color: '#aaa', fontSize: 14, cursor: 'pointer' },
};

export default Paywall;
