import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import type { MealPlanMonth } from "../lib/types";

export default function Plans() {
  const [months, setMonths] = useState<MealPlanMonth[]>([]);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  useEffect(() => {
    supabase
      .from("meal_plan_months")
      .select("*")
      .eq("is_published", true)
      .order("month_number")
      .then(({ data }) => {
        setMonths((data as MealPlanMonth[]) ?? []);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="spinner">Loading the year’s plans…</div>;

  return (
    <div className="screen">
      <div className="eyebrow">12-month rotation</div>
      <h1 style={{ marginBottom: 4 }}>The Pantry Year</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Twelve themed months built from ~15 core ingredients. Tap any month to see meals and recipes.
      </p>
      {months.map((m) => (
        <div key={m.id} className="card tap" onClick={() => nav(`/plans/${m.id}`)}>
          <div className="row">
            <div>
              <div className="meal-pill">Month {m.month_number}</div>
              <h2 style={{ margin: "2px 0 2px" }}>{m.title}</h2>
              <p className="muted">{m.theme}</p>
            </div>
            <span className="tag bulk">{m.target_kcal} kcal</span>
          </div>
        </div>
      ))}
    </div>
  );
}
