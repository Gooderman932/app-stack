import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { money } from "../lib/format";

interface Entry {
  id: string;
  entry_date: string;
  category: string;
  amount_cents: number;
  note: string | null;
}

export default function Budget() {
  const { user } = useAuth();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("groceries");
  const [note, setNote] = useState("");

  async function load() {
    if (!user) return;
    const { data } = await supabase
      .from("budget_tracker_entries")
      .select("*")
      .eq("profile_id", user.id)
      .order("entry_date", { ascending: false })
      .limit(60);
    setEntries((data as Entry[]) ?? []);
  }
  useEffect(() => {
    load();
  }, [user]);

  async function add() {
    if (!user || !amount) return;
    const cents = Math.round(parseFloat(amount) * 100);
    if (!Number.isFinite(cents)) return;
    await supabase.from("budget_tracker_entries").insert({
      profile_id: user.id,
      category,
      amount_cents: cents,
      note: note || null,
    });
    setAmount("");
    setNote("");
    load();
  }

  const total = entries.reduce((n, e) => n + e.amount_cents, 0);
  const days = new Set(entries.map((e) => e.entry_date)).size || 1;
  const perDay = total / days;

  return (
    <div className="screen">
      <div className="eyebrow">Track your spend vs. $5/day</div>
      <h1 style={{ marginBottom: 12 }}>Budget</h1>

      <div className="banner">
        <div className="row">
          <div>
            <div className="eyebrow">Avg / day</div>
            <div style={{ fontFamily: "Georgia, serif", fontSize: 30, color: "var(--grain)" }}>{money(perDay)}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="eyebrow">Total logged</div>
            <div style={{ color: "#bcd0c4", fontSize: 18 }}>{money(total)}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Log spending</h2>
        <input className="input" placeholder="Amount (e.g. 4.50)" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="groceries">Groceries</option>
          <option value="pantry_shop">Pantry shop order</option>
          <option value="produce">Fresh produce</option>
          <option value="other">Other</option>
        </select>
        <input className="input" placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="btn" onClick={add}>Add entry</button>
      </div>

      {entries.length === 0 ? (
        <div className="list-empty">No entries yet. Log your first grocery run above.</div>
      ) : (
        entries.map((e) => (
          <div key={e.id} className="card" style={{ padding: "10px 14px" }}>
            <div className="row">
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, textTransform: "capitalize" }}>{e.category.replace(/_/g, " ")}</div>
                <div className="muted">{e.entry_date}{e.note ? ` · ${e.note}` : ""}</div>
              </div>
              <span className="price">{money(e.amount_cents)}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
