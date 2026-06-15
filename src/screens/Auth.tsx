import { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function Auth() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setErr("");
    setBusy(true);
    try {
      if (mode === "in") await signIn(email.trim(), password);
      else await signUp(email.trim(), password, name.trim());
    } catch (e: any) {
      setErr(e.message ?? "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <div className="banner">
        <div className="eyebrow">Kansas Budget Meal Platform</div>
        <h1 style={{ color: "var(--grain)", marginTop: 6 }}>Eat well on $5 a day.</h1>
        <p className="muted" style={{ color: "#bcd0c4", marginTop: 6 }}>
          A full year of planned meals, lowest-cost shopping lists, and a cottage-food pantry shop.
        </p>
      </div>

      {err && <div className="err">{err}</div>}

      {mode === "up" && (
        <input className="input" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} />
      )}
      <input
        className="input"
        placeholder="Email"
        type="email"
        autoCapitalize="none"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        className="input"
        placeholder="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button className="btn" disabled={busy} onClick={submit}>
        {busy ? "Working…" : mode === "in" ? "Sign in" : "Create account"}
      </button>
      <button className="btn ghost" style={{ marginTop: 10 }} onClick={() => setMode(mode === "in" ? "up" : "in")}>
        {mode === "in" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}
