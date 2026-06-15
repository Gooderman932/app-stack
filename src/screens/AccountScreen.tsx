import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Purchases } from '@revenuecat/purchases-capacitor';
import { BILLING } from '../lib/billingConfig';
import Paywall from '../components/Paywall';

const AccountScreen: React.FC = () => {
  const { session, profile, signIn, signUp, signOut, isPremium } = useAuth();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [authError, setAuthError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);
  const [restoreMsg, setRestoreMsg] = useState('');

  const handleAuth = async () => {
    setLoading(true);
    setAuthError('');
    const result = mode === 'login'
      ? await signIn(email, password)
      : await signUp(email, password, name);
    if (result.error) setAuthError(result.error);
    setLoading(false);
  };

  const handleRestore = async () => {
    setRestoreMsg('');
    try {
      await Purchases.configure({ apiKey: BILLING.REVENUECAT_KEY });
      const restore = await Purchases.restorePurchases();
      const hasPremium = restore.customerInfo.entitlements.active[BILLING.ENTITLEMENT];
      setRestoreMsg(hasPremium ? '✓ Premium restored!' : 'No active subscription found.');
    } catch {
      setRestoreMsg('Restore failed — try again.');
    }
  };

  if (!session) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h1 style={styles.title}>{mode === 'login' ? 'Sign In' : 'Create Account'}</h1>
        </div>
        <div style={styles.form}>
          {mode === 'signup' && (
            <input style={styles.input} placeholder="Display Name" value={name} onChange={e => setName(e.target.value)} />
          )}
          <input style={styles.input} placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} type="email" autoCapitalize="none" />
          <input style={styles.input} placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} type="password" />
          {authError && <p style={styles.error}>{authError}</p>}
          <button onClick={handleAuth} disabled={loading} style={styles.btn}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
          <button onClick={() => setMode(m => m === 'login' ? 'signup' : 'login')} style={styles.switchBtn}>
            {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {showPaywall && <Paywall feature="Premium Plan" onClose={() => setShowPaywall(false)} />}
      <div style={styles.header}>
        <h1 style={styles.title}>Account</h1>
      </div>
      <div style={styles.profileCard}>
        <div style={styles.avatar}>{(profile?.display_name ?? profile?.email ?? '?')[0].toUpperCase()}</div>
        <div>
          <p style={styles.displayName}>{profile?.display_name ?? 'User'}</p>
          <p style={styles.profileEmail}>{profile?.email}</p>
          <span style={{ ...styles.tierBadge, background: isPremium ? '#4f8ef7' : '#333', color: isPremium ? '#fff' : '#aaa' }}>
            {isPremium ? '★ Premium' : 'Free Plan'}
          </span>
        </div>
      </div>

      {!isPremium && (
        <div style={styles.upgradeCard}>
          <p style={styles.upgradeText}>Unlock all 12 months, portion scaling, and batch-prep mode.</p>
          <button onClick={() => setShowPaywall(true)} style={styles.upgradeBtn}>Upgrade to Premium — $9.99/mo</button>
        </div>
      )}

      <div style={styles.section}>
        <button onClick={handleRestore} style={styles.menuItem}>Restore Purchases</button>
        {restoreMsg && <p style={{ fontSize: 13, color: restoreMsg.startsWith('✓') ? '#a0e0b0' : '#ff6b6b', padding: '4px 16px' }}>{restoreMsg}</p>}
        <button onClick={() => signOut()} style={{ ...styles.menuItem, color: '#ff6b6b' }}>Sign Out</button>
      </div>

      <div style={styles.legalSection}>
        <p style={styles.legalTitle}>Legal & Compliance</p>
        <button style={styles.legalLink} onClick={() => window.open('/privacy-policy.html', '_blank')}>Privacy Policy</button>
        <button style={styles.legalLink} onClick={() => window.open('/terms.html', '_blank')}>Terms of Service</button>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { paddingBottom: 100, background: '#0d0d1a', minHeight: '100vh', color: '#fff' },
  header: { padding: '24px 20px 16px', background: 'linear-gradient(135deg, #1a1a2e, #16213e)' },
  title: { margin: 0, fontSize: 24, fontWeight: 800 },
  form: { padding: '20px 16px' },
  input: { width: '100%', background: '#1e1e3f', border: '1px solid #2e2e5e', borderRadius: 10, color: '#fff', fontSize: 15, padding: '13px 14px', marginBottom: 12, boxSizing: 'border-box' as const, outline: 'none' },
  error: { color: '#ff6b6b', fontSize: 13, marginBottom: 12 },
  btn: { width: '100%', padding: '14px 0', background: '#4f8ef7', border: 'none', borderRadius: 10, color: '#fff', fontWeight: 700, fontSize: 16, cursor: 'pointer', marginBottom: 12 },
  switchBtn: { width: '100%', background: 'none', border: 'none', color: '#7ec8e3', fontSize: 14, cursor: 'pointer', textDecoration: 'underline' },
  profileCard: { display: 'flex', gap: 16, alignItems: 'center', margin: '16px 16px', background: '#1e1e3f', borderRadius: 14, padding: '18px 16px', border: '1px solid #2e2e5e' },
  avatar: { width: 52, height: 52, borderRadius: '50%', background: '#4f8ef7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 800, flexShrink: 0 },
  displayName: { margin: '0 0 2px', fontSize: 16, fontWeight: 700 },
  profileEmail: { margin: '0 0 8px', fontSize: 12, color: '#888' },
  tierBadge: { fontSize: 11, fontWeight: 700, borderRadius: 6, padding: '3px 8px', letterSpacing: 0.3 },
  upgradeCard: { margin: '0 16px 12px', background: 'linear-gradient(135deg, #1a2a4a, #1e1e3f)', borderRadius: 14, padding: '16px', border: '1px solid #2e5ea0' },
  upgradeText: { margin: '0 0 12px', fontSize: 14, color: '#ccc' },
  upgradeBtn: { width: '100%', padding: '12px 0', background: '#4f8ef7', border: 'none', borderRadius: 10, color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 14 },
  section: { margin: '8px 16px', background: '#1e1e3f', borderRadius: 14, overflow: 'hidden', border: '1px solid #2e2e5e' },
  menuItem: { display: 'block', width: '100%', padding: '15px 16px', background: 'none', border: 'none', borderBottom: '1px solid #2e2e5e', color: '#fff', fontSize: 15, textAlign: 'left' as const, cursor: 'pointer' },
  legalSection: { margin: '12px 16px', background: '#1a1a2e', borderRadius: 12, padding: '14px 16px', border: '1px solid #2e2e5e' },
  legalTitle: { margin: '0 0 10px', fontSize: 11, fontWeight: 700, color: '#555', letterSpacing: 1, textTransform: 'uppercase' as const },
  legalLink: { display: 'block', width: '100%', background: 'none', border: 'none', color: '#7ec8e3', fontSize: 14, textAlign: 'left' as const, cursor: 'pointer', padding: '6px 0', textDecoration: 'underline' },
};

export default AccountScreen;
