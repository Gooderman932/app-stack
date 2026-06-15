/** RevenueCat / Google Play Billing constants */
export const BILLING = {
  /** RevenueCat API key from VITE_REVENUECAT_GOOGLE_API_KEY env var */
  REVENUECAT_KEY: import.meta.env.VITE_REVENUECAT_GOOGLE_API_KEY ?? '',
  /** Google Play product ID for $9.99/mo subscription */
  PRODUCT_ID: 'premium_monthly',
  /** RevenueCat entitlement identifier */
  ENTITLEMENT: 'premium',
  /** RevenueCat offering identifier */
  OFFERING: 'default',
};
