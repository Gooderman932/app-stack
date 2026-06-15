import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { money } from "../lib/format";
import type { ProducerListing } from "../lib/types";

interface Ingredient { id: string; name: string; category: string; }

export default function Producer() {
  const { user } = useAuth();
  const [listings, setListings] = useState<ProducerListing[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("lb");
  const [price, setPrice] = useState("");

  async function load() {
    if (!user) return;
    const { data } = await supabase
      .from("producer_listings")
      .select("*, ingredients(name, category)")
      .eq("producer_id", user.id)
      .order("created_at", { ascending: false });
    setListings((data as ProducerListing[]) ?? []);
  }

  useEffect(() => {
    supabase.from("ingredients").select("id, name, category").order("name").then(({ data }) => {
      const list = (data as Ingredient[]) ?? [];
      setIngredients(list);
      if (list[0]) setIngredientId(list[0].id);
    });
    load();
  }, [user]);

  async function addListing() {
    if (!user || !ingredientId || !qty || !price) return;
    await supabase.from("producer_listings").insert({
      producer_id: user.id,
      ingredient_id: ingredientId,
      quantity_available: parseFloat(qty),
      unit,
      price_per_unit_cents: Math.round(parseFloat(price) * 100),
      status: "active",
    });
    setQty("");
    setPrice("");
    load();
  }

  async function setStatus(id: string, status: ProducerListing["status"]) {
    await supabase.from("producer_listings").update({ status }).eq("id", id);
    load();
  }

  return (
    <div className="screen">
      <div className="eyebrow">Producer dashboard</div>
      <h1 style={{ marginBottom: 12 }}>Your listings</h1>

      <div className="card">
        <h2>New bulk listing</h2>
        <select className="input" value={ingredientId} onChange={(e) => setIngredientId(e.target.value)}>
          {ingredients.map((i) => (
            <option key={i.id} value={i.id}>{i.name} ({i.category})</option>
          ))}
        </select>
        <div className="row" style={{ gap: 8 }}>
          <input className="input" style={{ flex: 2 }} placeholder="Qty available" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} />
          <select className="input" style={{ flex: 1 }} value={unit} onChange={(e) => setUnit(e.target.value)}>
            <option value="lb">lb</option>
            <option value="dozen">dozen</option>
            <option value="case">case</option>
            <option value="bushel">bushel</option>
          </select>
        </div>
        <input className="input" placeholder="Price per unit (e.g. 0.45)" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
        <button className="btn" disabled={!qty || !price} onClick={addListing}>List it</button>
      </div>

      {listings.length === 0 ? (
        <div className="list-empty">No listings yet. Add your first bulk item above.</div>
      ) : (
        listings.map((l) => (
          <div key={l.id} className="card">
            <div className="row">
              <div>
                <h2 style={{ margin: 0 }}>{l.ingredients?.name}</h2>
                <p className="muted">
                  {l.quantity_available} {l.unit} · {money(l.price_per_unit_cents)}/{l.unit}
                </p>
              </div>
              <span className={`tag ${l.status === "active" ? "bulk" : "self"}`}>{l.status}</span>
            </div>
            <div className="row" style={{ marginTop: 10, gap: 8 }}>
              <button className="btn ghost" style={{ padding: "7px 10px" }} onClick={() => setStatus(l.id, "active")}>Active</button>
              <button className="btn ghost" style={{ padding: "7px 10px" }} onClick={() => setStatus(l.id, "paused")}>Pause</button>
              <button className="btn ghost" style={{ padding: "7px 10px" }} onClick={() => setStatus(l.id, "sold_out")}>Sold out</button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
