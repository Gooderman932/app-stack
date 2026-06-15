import React, { useEffect, useState } from 'react';
import { Browser } from '@capacitor/browser';
import { supabase } from '../lib/supabase';
import { useCart } from '../context/CartContext';
import type { Product, ProductVariant } from '../lib/types';
import LoadingSpinner from '../components/LoadingSpinner';

interface ProductWithVariants extends Product {
  variants: ProductVariant[];
}

const CHECKOUT_URL = 'https://budgetmealplatform.com/checkout'; // replace with Stripe/Shopify checkout

const ShopScreen: React.FC = () => {
  const [products, setProducts] = useState<ProductWithVariants[]>([]);
  const [loading, setLoading] = useState(true);
  const { items, addItem, removeItem, updateQty, clearCart, total } = useCart();
  const [showCart, setShowCart] = useState(false);

  useEffect(() => {
    const load = async () => {
      const { data: prods } = await supabase.from('products').select('*').eq('is_active', true);
      if (!prods) { setLoading(false); return; }
      const enriched = await Promise.all(
        (prods as Product[]).map(async p => {
          const { data: vars } = await supabase.from('product_variants').select('*').eq('product_id', p.id);
          return { ...p, variants: (vars ?? []) as ProductVariant[] };
        })
      );
      setProducts(enriched);
      setLoading(false);
    };
    load();
  }, []);

  const handleCheckout = async () => {
    const params = new URLSearchParams({ items: JSON.stringify(items.map(i => ({ id: i.variantId, qty: i.quantity }))) });
    await Browser.open({ url: `${CHECKOUT_URL}?${params}` });
  };

  if (loading) return <LoadingSpinner message="Loading shop…" />;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Cottage Food Shop</h1>
        <p style={styles.sub}>Shelf-stable · Ships nationwide</p>
        {items.length > 0 && (
          <button onClick={() => setShowCart(true)} style={styles.cartBtn}>
            🛒 {items.reduce((s, i) => s + i.quantity, 0)} items · ${total.toFixed(2)}
          </button>
        )}
      </div>

      {showCart && (
        <div style={styles.cartOverlay}>
          <div style={styles.cartSheet}>
            <div style={styles.cartHeader}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Your Cart</h2>
              <button onClick={() => setShowCart(false)} style={styles.closeBtn}>✕</button>
            </div>
            {items.map(item => (
              <div key={item.variantId} style={styles.cartItem}>
                <div>
                  <p style={styles.cartName}>{item.name}</p>
                  <p style={styles.cartSize}>{item.sizeLabel}</p>
                </div>
                <div style={styles.cartControls}>
                  <button style={styles.qtyBtn} onClick={() => updateQty(item.variantId, item.quantity - 1)}>−</button>
                  <span style={{ fontSize: 14, width: 20, textAlign: 'center' }}>{item.quantity}</span>
                  <button style={styles.qtyBtn} onClick={() => updateQty(item.variantId, item.quantity + 1)}>+</button>
                  <span style={{ fontSize: 14, minWidth: 52, textAlign: 'right' }}>${(item.price * item.quantity).toFixed(2)}</span>
                </div>
              </div>
            ))}
            <div style={{ padding: '16px 16px 8px', borderTop: '1px solid #2e2e5e', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>Total</span>
              <span style={{ fontWeight: 700, fontSize: 18, color: '#a0e0b0' }}>${total.toFixed(2)}</span>
            </div>
            <div style={{ padding: '0 16px 16px', display: 'flex', gap: 10 }}>
              <button onClick={() => { clearCart(); setShowCart(false); }} style={styles.clearBtn}>Clear</button>
              <button onClick={handleCheckout} style={styles.checkoutBtn}>Checkout →</button>
            </div>
          </div>
        </div>
      )}

      <div style={styles.list}>
        {products.map(prod => (
          <div key={prod.id} style={styles.card}>
            <div style={styles.cardHeader}>
              {prod.image_url && <img src={prod.image_url} alt={prod.name} style={styles.img} />}
              <div>
                <h3 style={styles.prodName}>{prod.name}</h3>
                <p style={styles.prodDesc}>{prod.description}</p>
              </div>
            </div>
            <div style={styles.variants}>
              {prod.variants.map(v => (
                <div key={v.id} style={styles.variantRow}>
                  <span style={styles.varLabel}>{v.size_label}</span>
                  <span style={styles.varPrice}>${v.price_usd.toFixed(2)}</span>
                  <button
                    style={styles.addBtn}
                    onClick={() => addItem({ variantId: v.id, productId: prod.id, name: prod.name, sizeLabel: v.size_label, price: v.price_usd, quantity: 1 })}
                  >
                    Add
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { paddingBottom: 80, background: '#0d0d1a', minHeight: '100vh', color: '#fff' },
  header: { padding: '24px 20px 16px', background: 'linear-gradient(135deg, #1a1a2e, #16213e)' },
  title: { margin: 0, fontSize: 24, fontWeight: 800 },
  sub: { margin: '4px 0 0', color: '#a0e0b0', fontSize: 13 },
  cartBtn: { marginTop: 12, background: '#4f8ef7', border: 'none', borderRadius: 10, color: '#fff', fontWeight: 700, padding: '10px 18px', cursor: 'pointer', fontSize: 14 },
  cartOverlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 998, display: 'flex', alignItems: 'flex-end' },
  cartSheet: { background: '#1a1a2e', borderRadius: '16px 16px 0 0', width: '100%', maxHeight: '80vh', overflowY: 'auto', paddingBottom: 'env(safe-area-inset-bottom)' },
  cartHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 16px 12px', borderBottom: '1px solid #2e2e5e' },
  closeBtn: { background: 'none', border: 'none', color: '#888', fontSize: 18, cursor: 'pointer' },
  cartItem: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid #1e1e3f' },
  cartName: { margin: 0, fontSize: 14, fontWeight: 600 },
  cartSize: { margin: '2px 0 0', fontSize: 12, color: '#888' },
  cartControls: { display: 'flex', alignItems: 'center', gap: 8 },
  qtyBtn: { width: 28, height: 28, background: '#2e2e5e', border: 'none', borderRadius: 6, color: '#fff', fontSize: 16, cursor: 'pointer' },
  clearBtn: { flex: 1, padding: '12px 0', background: '#2e2e5e', border: 'none', borderRadius: 10, color: '#aaa', fontWeight: 700, cursor: 'pointer' },
  checkoutBtn: { flex: 2, padding: '12px 0', background: '#4f8ef7', border: 'none', borderRadius: 10, color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 15 },
  list: { padding: '16px' },
  card: { background: '#1e1e3f', borderRadius: 12, marginBottom: 12, overflow: 'hidden', border: '1px solid #2e2e5e' },
  cardHeader: { padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'flex-start' },
  img: { width: 56, height: 56, borderRadius: 8, objectFit: 'cover' },
  prodName: { margin: 0, fontSize: 16, fontWeight: 700 },
  prodDesc: { margin: '4px 0 0', fontSize: 12, color: '#aaa', lineHeight: 1.4 },
  variants: { borderTop: '1px solid #2e2e5e' },
  variantRow: { display: 'flex', alignItems: 'center', padding: '10px 16px', borderBottom: '1px solid #1a1a3a' },
  varLabel: { flex: 1, fontSize: 13 },
  varPrice: { fontSize: 14, fontWeight: 700, color: '#a0e0b0', marginRight: 12 },
  addBtn: { padding: '7px 18px', background: '#4f8ef7', border: 'none', borderRadius: 8, color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 13 },
};

export default ShopScreen;
