import { Capacitor } from '@capacitor/core';

// True only when running as a native Android app
export const isPlayBillingAvailable = () =>
  Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'android';

// Product IDs — must exactly match what you create in Play Console as Subscriptions
export const PLAY_PRODUCTS = {
  pro:  { id: 'stackpilot_pro_monthly',  type: 'SUBS', displayPrice: '$12.00/month', tier: 'pro'  },
  team: { id: 'stackpilot_team_monthly', type: 'SUBS', displayPrice: '$29.00/month', tier: 'team' },
};

let _plugin = null;

async function getPlugin() {
  if (!isPlayBillingAvailable()) return null;
  if (!_plugin) {
    const mod = await import('capacitor-billing');
    _plugin = mod.BillingPlugin;
  }
  return _plugin;
}

/**
 * Fetch product details from Google Play (price, title, billing period).
 * Returns null on web or if the product isn't published in Play Console yet.
 */
export async function queryProduct(productId, type = 'SUBS') {
  const plugin = await getPlugin();
  if (!plugin) return null;
  try {
    return await plugin.querySkuDetails({ product: productId, type });
  } catch (e) {
    console.warn('[Billing] queryProduct failed:', e?.message);
    return null;
  }
}

/**
 * Launch the Google Play billing sheet for a subscription.
 * Returns the purchase object (contains purchaseToken, orderId, productId, etc.).
 * Throws on user cancel or billing error.
 */
export async function purchaseSubscription(productId, type = 'SUBS') {
  const plugin = await getPlugin();
  if (!plugin) throw new Error('Google Play Billing is not available on this platform.');
  return await plugin.launchBillingFlow({ product: productId, type });
}

/**
 * Acknowledge a completed purchase. Google Play requires this within 3 days
 * or the purchase is automatically refunded.
 */
export async function acknowledgePurchase(purchaseToken) {
  const plugin = await getPlugin();
  if (!plugin || !purchaseToken) return;
  try {
    await plugin.sendAck({ purchaseToken });
  } catch (e) {
    console.warn('[Billing] acknowledgePurchase failed:', e?.message);
  }
}
