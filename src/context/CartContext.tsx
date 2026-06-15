import React, { createContext, useContext, useState } from 'react';
import type { CartItem } from '../lib/types';

interface CartCtx {
  items: CartItem[];
  addItem: (item: CartItem) => void;
  removeItem: (variantId: string) => void;
  updateQty: (variantId: string, qty: number) => void;
  clearCart: () => void;
  total: number;
}

const CartContext = createContext<CartCtx | null>(null);

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<CartItem[]>([]);

  const addItem = (item: CartItem) => {
    setItems(prev => {
      const existing = prev.find(i => i.variantId === item.variantId);
      if (existing) return prev.map(i => i.variantId === item.variantId ? { ...i, quantity: i.quantity + item.quantity } : i);
      return [...prev, item];
    });
  };

  const removeItem = (variantId: string) => setItems(prev => prev.filter(i => i.variantId !== variantId));
  const updateQty = (variantId: string, qty: number) => {
    if (qty <= 0) removeItem(variantId);
    else setItems(prev => prev.map(i => i.variantId === variantId ? { ...i, quantity: qty } : i));
  };
  const clearCart = () => setItems([]);
  const total = items.reduce((sum, i) => sum + i.price * i.quantity, 0);

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, updateQty, clearCart, total }}>
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used within CartProvider');
  return ctx;
};
