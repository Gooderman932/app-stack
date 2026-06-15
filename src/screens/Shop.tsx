import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import type { ShopProduct } from "../lib/types";
import { money } from "../lib/format";
import { openPhysicalCheckout, type CartLine } from "../lib/checkout";
import { useAuth } from "../context/AuthContext";

export default function Shop() {
  const { user } = useAuth();
  const [products, setProducts] = useState<ShopProduct[]>([]);
  const [cart, setCart] = useState<Record<string, CartLine>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    supabase
      .from("shop_products")
      .select("*, shop_product_variants(*)")
      .eq("active", true)
      .then(({ data }) => {
        setProducts((data as ShopProduct[]) ?? []);
        setLoading(false);
      });
  }, []);

  function add(variantId: string, sku: string) {
    setCart((c) => {
      const ex = c[variantId];
      return { ...c, [variantId]: { variantId, sku, quantity: (ex?.quantity ?? 0) + 1 } };
    });
  }

  const lines = Object.values(cart);
  const count = lines.reduce((n, l) => n + l.quantity, 0);

  async function checkout() {
    if (!user || lines.length === 0) return;
    setBusy(true);
    try {
      const { data, error } = await supabase
        .from("shop_orders")
        .insert({ customer_id: user.id, status: "pending" })
        .select()
        .single();
      if (error) throw error;
      await openPhysicalCheckout(data.id, lines);
      setCart({});
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="spinner">Loading the pantry shop…</div>;

  return (
    <div className="screen">
      <div className="eyebrow">Cottage-food pantry · ships nationwide</div>
      <h1 style={{ marginBottom: 4 }}>The Shop</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Shelf-stable dry mixes, spice blends, and granola — all Kansas cottage-food compliant.
      </p>
      {products.map((p) => (
        <div key={p.id} className="card">
          <h2 style={{ marginBottom: 2 }}>{p.name}</h2>
          <p className="muted" style={{ marginBottom: 8 }}>{p.description}</p>
          {p.allergen_info?.length > 0 && (
            <p style={{ fontSize: 12, color: "var(--rust)", marginBottom: 8 }}>
              Allergens: {p.allergen_info.join(", ").replace(/_/g, " ")}
            </p>
          )}
          {p.shop_product_variants
            .sort((a, b) => a.price_cents - b.price_cents)
            .map((v) => (
              <div key={v.id} className="row" style={{ padding: "6px 0" }}>
                <span style={{ fontSize: 14 }}>{v.variant_name}</span>
                <span className="row" style={{ width: "auto", gap: 10 }}>
                  <span className="price">{money(v.price_cents)}</span>
                  <button
                    className="btn alt"
                    style={{ width: "auto", padding: "7px 12px" }}
                    onClick={() => add(v.id, p.sku)}
                  >
                    Add
                  </button>
                </span>
              </div>
            ))}
        </div>
      ))}

      {count > 0 && (
        <button className="btn" disabled={busy} onClick={checkout}>
          {busy ? "Starting checkout…" : `Check out (${count} item${count > 1 ? "s" : ""})`}
        </button>
      )}
      <p className="muted" style={{ textAlign: "center", marginTop: 10, fontSize: 12 }}>
        Physical goods are paid through secure external checkout, per Google Play policy.
      </p>
    </div>
  );
}
