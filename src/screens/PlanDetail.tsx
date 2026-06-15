import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import Paywall from "../components/Paywall";
import type { MealPlanMonth, MealSlot, MealIngredient, RecipeCard } from "../lib/types";

export default function PlanDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { premium } = useAuth();
  const [month, setMonth] = useState<MealPlanMonth | null>(null);
  const [slots, setSlots] = useState<MealSlot[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [ings, setIngs] = useState<Record<string, MealIngredient[]>>({});
  const [recipe, setRecipe] = useState<Record<string, string>>({});
  const [servings, setServings] = useState(1); // premium portion scaling

  useEffect(() => {
    if (!id) return;
    supabase.from("meal_plan_months").select("*").eq("id", id).maybeSingle().then(({ data }) =>
      setMonth(data as MealPlanMonth | null)
    );
    supabase
      .from("meal_slots")
      .select("*")
      .eq("plan_month_id", id)
      .order("day_number")
      .order("meal_type")
      .then(({ data }) => setSlots((data as MealSlot[]) ?? []));
  }, [id]);

  async function toggle(slotId: string) {
    if (open === slotId) {
      setOpen(null);
      return;
    }
    setOpen(slotId);
    if (!ings[slotId]) {
      const { data } = await supabase
        .from("meal_ingredients")
        .select("*, ingredients(name, category)")
        .eq("meal_slot_id", slotId);
      setIngs((p) => ({ ...p, [slotId]: (data as MealIngredient[]) ?? [] }));
    }
    if (!recipe[slotId]) {
      const { data } = await supabase
        .from("recipe_cards")
        .select("*")
        .eq("meal_slot_id", slotId)
        .order("version", { ascending: false })
        .limit(1)
        .maybeSingle();
      setRecipe((p) => ({ ...p, [slotId]: (data as RecipeCard | null)?.content ?? "" }));
    }
  }

  const scale = premium ? servings : 1;
  const fmtQty = (q: number) => {
    const v = q * scale;
    return Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, "");
  };

  return (
    <div className="screen">
      <button className="btn ghost" style={{ width: "auto", padding: "6px 12px", marginBottom: 14 }} onClick={() => nav(-1)}>
        ← Back
      </button>
      {month && (
        <>
          <div className="eyebrow">Month {month.month_number}</div>
          <h1>{month.title}</h1>
          <p className="muted" style={{ margin: "8px 0 16px" }}>{month.description}</p>
        </>
      )}

      {/* Premium: portion scaling */}
      {premium ? (
        <div className="card">
          <div className="row">
            <div>
              <span className="meal-pill">Premium</span>
              <h2 style={{ margin: "2px 0" }}>Portion scaling</h2>
              <p className="muted">Quantities below adjust to your household.</p>
            </div>
            <div className="row" style={{ width: "auto", gap: 10 }}>
              <button className="btn ghost" style={{ width: 40, padding: 8 }} onClick={() => setServings((s) => Math.max(1, s - 1))}>−</button>
              <strong style={{ minWidth: 18, textAlign: "center" }}>{servings}</strong>
              <button className="btn ghost" style={{ width: 40, padding: 8 }} onClick={() => setServings((s) => Math.min(12, s + 1))}>+</button>
            </div>
          </div>
        </div>
      ) : (
        <Paywall feature="Portion scaling & batch-prep" />
      )}

      {slots.map((s) => (
        <div key={s.id} className="card tap" onClick={() => toggle(s.id)}>
          <div className="row">
            <div>
              <span className="meal-pill">{s.meal_type}{s.day_number > 1 ? ` · day ${s.day_number}` : ""}</span>
              <h2 style={{ margin: "2px 0" }}>{s.name}</h2>
              <p className="muted">
                {s.target_kcal ? `${s.target_kcal} kcal` : ""}{s.prep_time_minutes ? ` · ${s.prep_time_minutes} min` : ""}
              </p>
            </div>
            <span>{open === s.id ? "▲" : "▼"}</span>
          </div>
          {open === s.id && (
            <div style={{ marginTop: 12 }} onClick={(e) => e.stopPropagation()}>
              <h2 style={{ fontSize: 15 }}>
                Ingredients{premium && scale > 1 ? ` · ×${scale}` : ""}
              </h2>
              {(ings[s.id] ?? []).map((mi) => (
                <div key={mi.id} className="ingredient-line">
                  <span>{mi.ingredients?.name}{mi.notes ? ` — ${mi.notes}` : ""}</span>
                  <span className="muted">{fmtQty(mi.quantity)} {mi.unit}</span>
                </div>
              ))}
              {recipe[s.id] && (
                <>
                  <h2 style={{ fontSize: 15, marginTop: 14 }}>Method</h2>
                  <p className="recipe">{recipe[s.id]}</p>
                  {premium && (
                    <div className="card" style={{ background: "var(--grain)", marginTop: 12 }}>
                      <span className="meal-pill">Batch-prep mode</span>
                      <p style={{ fontSize: 13, marginTop: 4 }}>
                        Cook {scale > 1 ? `${scale} servings` : "a double batch"} on Sunday: multiply each quantity above,
                        cook grains and legumes in one pot, portion into containers, and refrigerate up to 5 days
                        (or freeze 2–3 day portions).
                      </p>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
