import React, { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';
import type { ProducerListing, ProducerProfile } from '../lib/types';
import LoadingSpinner from '../components/LoadingSpinner';

interface ListingWithProducer extends ProducerListing {
  producer: ProducerProfile | null;
}

const ProducersScreen: React.FC = () => {
  const { session, profile } = useAuth();
  const [listings, setListings] = useState<ListingWithProducer[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'browse' | 'join'>('browse');
  // Join form
  const [farmName, setFarmName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [city, setCity] = useState('');
  const [zipCode, setZipCode] = useState('');
  const [bio, setBio] = useState('');
  const [joining, setJoining] = useState(false);
  const [joinMsg, setJoinMsg] = useState('');

  useEffect(() => {
    const load = async () => {
      const { data: listData } = await supabase.from('producer_listings').select('*').eq('is_active', true).limit(50);
      if (!listData) { setLoading(false); return; }
      const enriched: ListingWithProducer[] = await Promise.all(
        (listData as ProducerListing[]).map(async l => {
          const { data: prod } = await supabase.from('producer_profiles').select('*').eq('id', l.producer_id).maybeSingle();
          return { ...l, producer: (prod ?? null) as ProducerProfile | null };
        })
      );
      setListings(enriched);
      setLoading(false);
    };
    load();
  }, []);

  const handleJoin = async () => {
    if (!session) { setJoinMsg('Sign in first to register as a producer.'); return; }
    if (!farmName || !zipCode) { setJoinMsg('Farm name and zip code are required.'); return; }
    setJoining(true);
    const { error } = await supabase.from('producer_profiles').insert({
      user_id: session.user.id,
      farm_name: farmName,
      contact_email: contactEmail || profile?.email || '',
      city,
      zip_code: zipCode,
      bio,
      is_approved: false,
      certifications: [],
    });
    setJoining(false);
    setJoinMsg(error ? `Error: ${error.message}` : '✓ Application submitted — we review within 48 hours.');
  };

  const pipelineLabel: Record<string, string> = {
    national_bulk: 'National Bulk',
    regional_fresh: 'Regional Fresh',
    producer_direct: 'Producer Direct',
    customer_self_source: 'Self Source',
    not_eligible: 'Not Eligible',
  };

  const pipelineColor: Record<string, string> = {
    national_bulk: '#4f8ef7',
    regional_fresh: '#a0e0b0',
    producer_direct: '#f7c74f',
    customer_self_source: '#888',
    not_eligible: '#ff6b6b',
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Kansas Producer Network</h1>
        <p style={styles.sub}>Local suppliers · Bulk ingredients · Compliant pipelines</p>
        <div style={styles.tabRow}>
          <button style={{ ...styles.tabBtn, ...(tab === 'browse' ? styles.tabActive : {}) }} onClick={() => setTab('browse')}>Browse Listings</button>
          <button style={{ ...styles.tabBtn, ...(tab === 'join' ? styles.tabActive : {}) }} onClick={() => setTab('join')}>Join as Producer</button>
        </div>
      </div>

      {tab === 'browse' && (
        <div style={styles.content}>
          {loading ? <LoadingSpinner message="Loading listings…" /> : listings.length === 0 ? (
            <p style={styles.empty}>No active listings yet. Be the first producer to join!</p>
          ) : listings.map(l => (
            <div key={l.id} style={styles.card}>
              <div style={styles.cardTop}>
                <div>
                  <h3 style={styles.ingName}>{l.ingredient_name}</h3>
                  {l.producer && <p style={styles.farmName}>{l.producer.farm_name} · {l.producer.city ?? 'KS'}</p>}
                </div>
                <span style={{ ...styles.pipeline, color: pipelineColor[l.pipeline] ?? '#aaa', borderColor: pipelineColor[l.pipeline] ?? '#aaa' }}>
                  {pipelineLabel[l.pipeline] ?? l.pipeline}
                </span>
              </div>
              {l.description && <p style={styles.desc}>{l.description}</p>}
              <div style={styles.details}>
                {l.quantity_available_lbs && <span style={styles.detail}>{l.quantity_available_lbs} lbs available</span>}
                {l.price_per_lb_usd && <span style={styles.detailHighlight}>${l.price_per_lb_usd.toFixed(2)}/lb</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'join' && (
        <div style={styles.content}>
          <p style={styles.joinIntro}>Register your Kansas farm or food operation to list bulk ingredients for purchase by the platform network.</p>
          {joinMsg && <p style={{ ...styles.joinMsg, color: joinMsg.startsWith('✓') ? '#a0e0b0' : '#ff6b6b' }}>{joinMsg}</p>}
          <input style={styles.input} placeholder="Farm / Business Name *" value={farmName} onChange={e => setFarmName(e.target.value)} />
          <input style={styles.input} placeholder="Contact Email" value={contactEmail} onChange={e => setContactEmail(e.target.value)} type="email" />
          <input style={styles.input} placeholder="City" value={city} onChange={e => setCity(e.target.value)} />
          <input style={styles.input} placeholder="Zip Code (KS) *" value={zipCode} onChange={e => setZipCode(e.target.value)} />
          <textarea style={{ ...styles.input, height: 80, resize: 'none' }} placeholder="Tell us about your operation (optional)" value={bio} onChange={e => setBio(e.target.value)} />
          <button onClick={handleJoin} disabled={joining} style={styles.joinBtn}>{joining ? 'Submitting…' : 'Apply to Join'}</button>
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { paddingBottom: 80, background: '#0d0d1a', minHeight: '100vh', color: '#fff' },
  header: { padding: '24px 20px 0', background: 'linear-gradient(135deg, #1a1a2e, #16213e)' },
  title: { margin: 0, fontSize: 24, fontWeight: 800 },
  sub: { margin: '4px 0 16px', color: '#f7c74f', fontSize: 13 },
  tabRow: { display: 'flex', gap: 0, borderTop: '1px solid #2e2e5e' },
  tabBtn: { flex: 1, padding: '12px 0', background: 'none', border: 'none', color: '#888', fontWeight: 600, fontSize: 13, cursor: 'pointer', borderBottom: '2px solid transparent' },
  tabActive: { color: '#4f8ef7', borderBottom: '2px solid #4f8ef7' },
  content: { padding: '16px' },
  empty: { color: '#888', fontSize: 14, textAlign: 'center', padding: '32px 0' },
  card: { background: '#1e1e3f', borderRadius: 12, padding: '14px 16px', marginBottom: 12, border: '1px solid #2e2e5e' },
  cardTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 },
  ingName: { margin: 0, fontSize: 15, fontWeight: 700 },
  farmName: { margin: '2px 0 0', fontSize: 12, color: '#888' },
  pipeline: { fontSize: 10, fontWeight: 700, letterSpacing: 0.5, border: '1px solid', borderRadius: 6, padding: '2px 7px', flexShrink: 0, marginLeft: 8 },
  desc: { fontSize: 13, color: '#bbb', margin: '0 0 8px', lineHeight: 1.5 },
  details: { display: 'flex', gap: 12, flexWrap: 'wrap' },
  detail: { fontSize: 12, color: '#888' },
  detailHighlight: { fontSize: 14, fontWeight: 700, color: '#a0e0b0' },
  joinIntro: { fontSize: 14, color: '#bbb', lineHeight: 1.6, marginBottom: 20 },
  joinMsg: { fontSize: 13, marginBottom: 12, padding: '10px 14px', background: '#1a1a3a', borderRadius: 8 },
  input: { width: '100%', background: '#1e1e3f', border: '1px solid #2e2e5e', borderRadius: 10, color: '#fff', fontSize: 14, padding: '12px 14px', marginBottom: 12, boxSizing: 'border-box' as const, outline: 'none' },
  joinBtn: { width: '100%', padding: '14px 0', background: '#4f8ef7', border: 'none', borderRadius: 10, color: '#fff', fontWeight: 700, fontSize: 16, cursor: 'pointer' },
};

export default ProducersScreen;
