// External checkout for PHYSICAL cottage-food goods.
// Google Play policy forbids selling physical goods through Play Billing, so we
// open a hosted checkout (Stripe/Shopify) in the system browser.
import { Browser } from "@capacitor/browser";

export interface CartLine {
  variantId: string;
  sku: string;
  quantity: number;
}

export async function openPhysicalCheckout(orderId: string, lines: CartLine[]): Promise<void> {
  const base = import.meta.env.VITE_SHOP_CHECKOUT_BASE_URL as string;
  const payload = encodeURIComponent(JSON.stringify({ orderId, lines }));
  await Browser.open({ url: `${base}/checkout?order=${orderId}&items=${payload}` });
}
