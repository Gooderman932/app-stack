import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { purchasePremium } from "../lib/billing";
import { BILLING, PREMIUM_FEATURES } from "../lib/billingConfig";

// Inline upsell shown where a premium feature would appear.
export default function Paywall({ feature }: { feature: string }) {
  const { refreshPremium } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function buy() {
    setBusy(true);
    setErr("");
    try {
      await purchasePremium();
      await refreshPremium();
    } catch (e: any) {
      setErr(e.message ?? "Purchase unavailable in this build.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="banner" style={{ marginTop: 12 }}>
      <div className="eyebrow">Premium · {BILLING.priceDisplay}</div>
      <h2 style={{ color: "var(--grain)", margin: "6px 0" }}>{feature} is a premium feature</h2>
      <ul className="muted" style={{ color: "#bcd0c4", margin: "0 0 12px 18px", fontSize: 13 }}>
        {PREMIUM_FEATURES.map((f) => (
          <li key={f} style={{ marginBottom: 3 }}>{f}</li>
        ))}
      </ul>
      {err && <div className="err">{err}</div>}
      <button className="btn alt" disabled={busy} onClick={buy}>
        {busy ? "Opening Google Play…" : `Subscribe — ${BILLING.priceDisplay}`}
      </button>
    </div>
  );
}
