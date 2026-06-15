// Google Play Billing via RevenueCat (industry-standard wrapper over Play Billing v6+).
// Digital subscriptions (premium meal-plan tier) MUST use Play Billing per Google policy.
// Physical cottage-food goods must NOT use Play Billing — see lib/checkout.ts.
import { Capacitor } from "@capacitor/core";
import {
  Purchases,
  LOG_LEVEL,
  type CustomerInfo,
  type PurchasesOfferings,
} from "@revenuecat/purchases-capacitor";

import { BILLING } from "./billingConfig";
const ENTITLEMENT_PREMIUM = BILLING.entitlementId;

let configured = false;

export async function initBilling(appUserId?: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) return; // billing only runs on-device
  if (configured) return;
  const apiKey = import.meta.env.VITE_REVENUECAT_ANDROID_KEY as string;
  if (!apiKey || apiKey.startsWith("goog_REPLACE")) {
    console.warn("RevenueCat key not set; subscriptions disabled in this build.");
    return;
  }
  await Purchases.setLogLevel({ level: LOG_LEVEL.WARN });
  await Purchases.configure({ apiKey, appUserID: appUserId });
  configured = true;
}

export async function getOfferings(): Promise<PurchasesOfferings | null> {
  if (!Capacitor.isNativePlatform() || !configured) return null;
  return Purchases.getOfferings();
}

export async function isPremium(): Promise<boolean> {
  if (!Capacitor.isNativePlatform() || !configured) return false;
  const { customerInfo } = await Purchases.getCustomerInfo();
  return entitled(customerInfo);
}

export async function purchasePremium(): Promise<boolean> {
  if (!Capacitor.isNativePlatform() || !configured) return false;
  const offerings = await Purchases.getOfferings();
  const pkg = offerings.current?.availablePackages?.[0];
  if (!pkg) throw new Error("No subscription package configured in RevenueCat.");
  const { customerInfo } = await Purchases.purchasePackage({ aPackage: pkg });
  return entitled(customerInfo);
}

export async function restorePurchases(): Promise<boolean> {
  if (!Capacitor.isNativePlatform() || !configured) return false;
  const { customerInfo } = await Purchases.restorePurchases();
  return entitled(customerInfo);
}

function entitled(info: CustomerInfo): boolean {
  return info.entitlements.active[ENTITLEMENT_PREMIUM] !== undefined;
}
