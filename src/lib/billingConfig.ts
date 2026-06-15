// Single source of truth for the subscription product.
// These IDs must match exactly across Play Console and RevenueCat.
export const BILLING = {
  // Google Play Console > Monetize > Subscriptions
  productId: "premium_monthly",
  basePlanId: "monthly-autorenew",
  priceDisplay: "$9.99/mo",
  // RevenueCat > Entitlements
  entitlementId: "premium",
  // RevenueCat > Offerings (the "current" offering is used by default)
  offeringId: "default",
} as const;

export const PREMIUM_FEATURES = [
  "Allergy & dietary swaps on every recipe",
  "Portion scaling for households of any size",
  "Batch-prep mode with Sunday cook plans",
  "Lowest-cost shopping lists synced to your ZIP",
] as const;
