import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";

export default function ProducerSignup() {
  const { user, profile } = useAuth();
  const nav = useNavigate();
  const [farm, setFarm] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (profile?.role === "producer") {
    nav("/producer", { replace: true });
  }

  async function apply() {
    if (!user) return;
    setBusy(true);
    setErr("");
    try {
      const { error: pe } = await supabase
        .from("producer_profiles")
        .upsert({ id: user.id, farm_name: farm, city, zip_code: zip, state_code: "KS", description: desc });
      if (pe) throw pe;
      const { error: re } = await supabase.from("profiles").update({ role: "producer" }).eq("id", user.id);
      if (re) throw re;
      nav("/producer", { replace: true });
    } catch (e: any) {
      setErr(e.message ?? "Could not submit.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <div className="eyebrow">Kansas Producer Network</div>
      <h1 style={{ marginBottom: 6 }}>Sell your harvest</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        List bulk ingredients for the platform to distribute. Shelf-stable goods reach national buyers;
        fresh produce serves regional fulfillment.
      </p>
      {err && <div className="err">{err}</div>}
      <input className="input" placeholder="Farm / business name" value={farm} onChange={(e) => setFarm(e.target.value)} />
      <input className="input" placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
      <input className="input" placeholder="ZIP code" value={zip} onChange={(e) => setZip(e.target.value)} />
      <textarea className="input" rows={3} placeholder="What do you grow / produce?" value={desc} onChange={(e) => setDesc(e.target.value)} />
      <button className="btn" disabled={busy || !farm} onClick={apply}>
        {busy ? "Submitting…" : "Join the network"}
      </button>
    </div>
  );
}
