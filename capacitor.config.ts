import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.poordude.budgetmeal",
  appName: "Budget Meal Platform",
  webDir: "dist",
  android: {
    allowMixedContent: false,
  },
  plugins: {
    // RevenueCat configures Google Play Billing at runtime (see src/lib/billing.ts).
  },
};

export default config;
