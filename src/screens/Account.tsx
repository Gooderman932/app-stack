import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { purchasePremium, restorePurchases } from "../lib/billing";

export default function Account() {
  const { user, profile, premium, signOut, refreshPremium } = useAuth();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function buy() {
    setBusy(true);
    setMsg("");
    try {
      const ok = await purchasePremium();
      await refreshPremium();
      setMsg(ok ? "Premium active. Enjoy!" : "Purchase not completed.");
    } catch (e: any) {
      setMsg(e.message ?? "Purchase unavailable in this build.");
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    setBusy(true);
    setMsg("");
    try {
      await restorePurchases();
      await refreshPremium();
      setMsg("Purchases restored.");
    } catch {
      setMsg("Nothing to restore.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <div className="eyebrow">Account</div>
      <h1 style={{ marginBottom: 12 }}>{profile?.full_name ?? "Your account"}</h1>

      <div className="card">
        <p className="muted">Signed in as</p>
        <p style={{ fontWeight: 600 }}>{user?.email}</p>
        <p className="muted" style={{ marginTop: 6, textTransform: "capitalize" }}>Role: {profile?.role}</p>
      </div>

      <div className="banner">
        <div className="eyebrow">{premium ? "Premium member" : "Premium meal planning"}</div>
        <h2 style={{ color: "var(--grain)", margin: "6px 0" }}>
          {premium ? "All features unlocked" : "Unlock personalization"}
        </h2>
        <p className="muted" style={{ color: "#bcd0c4", marginBottom: 12 }}>
          Allergy swaps, portion scaling, batch-prep mode, and lowest-cost shopping lists synced to your region.
        </p>
        {!premium && (
          <button className="btn alt" disabled={busy} onClick={buy}>
            {busy ? "Opening Google Play…" : "Subscribe with Google Play"}
          </button>
        )}
        <button className="btn ghost" style={{ marginTop: 10, color: "var(--grain)", borderColor: "var(--grain)" }} disabled={busy} onClick={restore}>
          Restore purchases
        </button>
        {msg && <p className="muted" style={{ color: "#bcd0c4", marginTop: 10 }}>{msg}</p>}
      </div>

      <button className="btn ghost" onClick={signOut}>Sign out</button>
      <p className="muted" style={{ textAlign: "center", marginTop: 14, fontSize: 11 }}>
        Subscriptions are billed by Google Play. Manage or cancel anytime in the Play Store.
      </p>
    </div>
  );
}
