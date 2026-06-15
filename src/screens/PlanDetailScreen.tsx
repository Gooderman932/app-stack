import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';
import Paywall from '../components/Paywall';
import LoadingSpinner from '../components/LoadingSpinner';
import type { MealPlan, MealSlot, MealIngredient, RecipeCard } from '../lib/types';

interface SlotWithData extends MealSlot {
  ingredients: MealIngredient[];
  recipe: RecipeCard | null;
}

const PlanDetailScreen: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isPremium } = useAuth();
  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [slots, setSlots] = useState<SlotWithData[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [servings, setServings] = useState(2);
  const [batchMode, setBatchMode] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);
  const [paywallFeature, setPaywallFeature] = useState('');

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      const [{ data: planData }, { data: slotData }] = await Promise.all([
        supabase.from('meal_plans').select('*').eq('id', id).single(),
        supabase.from('meal_slots').select('*').eq('meal_plan_id', id),
      ]);
      if (!planData || !slotData) { setLoading(false); return; }
      setPlan(planData as MealPlan);
      const enriched: SlotWithData[] = await Promise.all(
        (slotData as MealSlot[]).map(async slot => {
          const [{ data: ings }, { data: rec }] = await Promise.all([
            supabase.from('meal_ingredients').select('*').eq('meal_slot_id', slot.id),
            supabase.from('recipe_cards').select('*').eq('meal_slot_id', slot.id).maybeSingle(),
          ]);
          return { ...slot, ingredients: (ings ?? []) as MealIngredient[], recipe: (rec ?? null) as RecipeCard | null };
        })
      );
      setSlots(enriched);
      setLoading(false);
    };
    load();
  }, [id]);

  const requirePremium = (feature: string, action: () => void) => {
    if (isPremium) { action(); return; }
    setPaywallFeature(feature);
    setShowPaywall(true);
  };

  if (loading) return <LoadingSpinner message="Loading plan details…" />;
  if (!plan) return <div style={{ color: '#fff', padding: 24 }}>Plan not found.</div>;

  return (
    <div style={styles.container}>
      {showPaywall && <Paywall feature={paywallFeature} onClose={() => setShowPaywall(false)} />}
      <div style={styles.header}>
        <button onClick={() => navigate(-1)} style={styles.back}>← Back</button>
        <h1 style={styles.title}>{plan.title}</h1>
        {plan.theme && <p style={styles.theme}>{plan.theme}</p>}
        {plan.description && <p style={styles.desc}>{plan.description}</p>}
      </div>

      {/* Premium controls */}
      <div style={styles.controls}>
        <div style={styles.controlRow}>
          <span style={styles.controlLabel}>Servings</span>
          <div style={styles.stepperRow}>
            <button style={styles.stepper} onClick={() => requirePremium('Portion Scaling', () => setServings(s => Math.max(1, s - 1)))}>−</button>
            <span style={styles.stepperVal}>{servings}</span>
            <button style={styles.stepper} onClick={() => requirePremium('Portion Scaling', () => setServings(s => Math.min(10, s + 1)))}>+</button>
            {!isPremium && <span style={styles.premiumTag}>Premium</span>}
          </div>
        </div>
        <div style={styles.controlRow}>
          <span style={styles.controlLabel}>Batch-Prep Mode</span>
          <div style={styles.stepperRow}>
            <button
              style={{ ...styles.toggle, ...(batchMode ? styles.toggleOn : {}) }}
              onClick={() => requirePremium('Batch-Prep Mode', () => setBatchMode(b => !b))}
            >
              {batchMode ? 'ON' : 'OFF'}
            </button>
            {!isPremium && <span style={styles.premiumTag}>Premium</span>}
          </div>
        </div>
      </div>

      {batchMode && isPremium && (
        <div style={styles.batchBanner}>
          🥘 Batch-Prep: Cook Sunday for the week. Quantities scaled ×{servings}.
        </div>
      )}

      {/* Meal slots */}
      {slots.map(slot => (
        <div key={slot.id} style={styles.slot}>
          <button style={styles.slotHeader} onClick={() => setExpanded(e => e === slot.id ? null : slot.id)}>
            <div>
              <span style={styles.slotType}>{slot.meal_type.toUpperCase()}</span>
              <p style={styles.slotLabel}>{slot.slot_label}</p>
            </div>
            <div style={styles.slotRight}>
              {slot.estimated_cost_usd && (
                <span style={styles.cost}>${(slot.estimated_cost_usd * servings / 2).toFixed(2)}</span>
              )}
              <span style={styles.chevron}>{expanded === slot.id ? '▲' : '▼'}</span>
            </div>
          </button>
          {expanded === slot.id && (
            <div style={styles.slotBody}>
              <h4 style={styles.sectionHead}>Ingredients</h4>
              {slot.ingredients.map(ing => (
                <div key={ing.id} style={styles.ingRow}>
                  <span style={styles.ingName}>{ing.ingredient_name}</span>
                  <span style={styles.ingQty}>{ing.notes ?? `${ing.quantity}${ing.unit ? ' ' + ing.unit : ''}`}</span>
                </div>
              ))}
              {slot.recipe && (
                <>
                  <h4 style={styles.sectionHead}>Recipe — {slot.recipe.title}</h4>
                  <p style={styles.recipeTime}>
                    Prep {slot.recipe.prep_minutes ?? '?'}min · Cook {slot.recipe.cook_minutes ?? '?'}min
                  </p>
                  {slot.recipe.instructions.map((step, i) => (
                    <p key={i} style={styles.step}>{i + 1}. {step}</p>
                  ))}
                  {slot.recipe.tips && <p style={styles.tips}>💡 {slot.recipe.tips}</p>}
                </>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { paddingBottom: 100, background: '#0d0d1a', minHeight: '100vh', color: '#fff' },
  header: { padding: '16px 20px 20px', background: 'linear-gradient(135deg, #1a1a2e, #16213e)' },
  back: { background: 'none', border: 'none', color: '#7ec8e3', fontSize: 14, cursor: 'pointer', padding: '0 0 8px', marginLeft: -4 },
  title: { margin: '0 0 4px', fontSize: 22, fontWeight: 800 },
  theme: { margin: 0, color: '#7ec8e3', fontSize: 13 },
  desc: { margin: '8px 0 0', color: '#bbb', fontSize: 13, lineHeight: 1.5 },
  controls: { margin: '16px 16px', background: '#1e1e3f', borderRadius: 12, overflow: 'hidden' },
  controlRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderBottom: '1px solid #2e2e5e' },
  controlLabel: { fontSize: 14, fontWeight: 600 },
  stepperRow: { display: 'flex', alignItems: 'center', gap: 8 },
  stepper: { width: 32, height: 32, background: '#2e2e5e', border: 'none', borderRadius: 8, color: '#fff', fontSize: 18, cursor: 'pointer' },
  stepperVal: { width: 24, textAlign: 'center', fontSize: 16, fontWeight: 700 },
  toggle: { padding: '6px 14px', background: '#333', border: 'none', borderRadius: 8, color: '#aaa', fontWeight: 700, cursor: 'pointer', fontSize: 13 },
  toggleOn: { background: '#4f8ef7', color: '#fff' },
  premiumTag: { fontSize: 10, color: '#f7c74f', fontWeight: 700, border: '1px solid #f7c74f', borderRadius: 4, padding: '1px 5px' },
  batchBanner: { margin: '0 16px 8px', background: '#1a3a2e', borderRadius: 10, padding: '10px 14px', fontSize: 13, color: '#a0e0b0', border: '1px solid #2a5a3e' },
  slot: { margin: '8px 16px', background: '#1e1e3f', borderRadius: 12, overflow: 'hidden' },
  slotHeader: { width: '100%', background: 'none', border: 'none', padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', color: '#fff', textAlign: 'left' },
  slotType: { fontSize: 10, fontWeight: 700, letterSpacing: 1, color: '#7ec8e3' },
  slotLabel: { margin: '2px 0 0', fontSize: 14, fontWeight: 600 },
  slotRight: { display: 'flex', alignItems: 'center', gap: 10 },
  cost: { fontSize: 14, fontWeight: 700, color: '#a0e0b0' },
  chevron: { color: '#555', fontSize: 12 },
  slotBody: { borderTop: '1px solid #2e2e5e', padding: '14px 16px' },
  sectionHead: { margin: '8px 0 8px', fontSize: 12, fontWeight: 700, color: '#7ec8e3', textTransform: 'uppercase', letterSpacing: 0.8 },
  ingRow: { display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid #1a1a3a' },
  ingName: { fontSize: 13 },
  ingQty: { fontSize: 12, color: '#aaa' },
  recipeTime: { fontSize: 12, color: '#888', margin: '0 0 8px' },
  step: { fontSize: 13, lineHeight: 1.6, color: '#ccc', margin: '0 0 6px' },
  tips: { background: '#1a2a1a', borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#a0e0b0', margin: '8px 0 0' },
};

export default PlanDetailScreen;
