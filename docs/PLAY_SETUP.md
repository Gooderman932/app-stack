# Google Play Console Setup Guide
## Budget Meal Platform — $9.99/mo Subscription

### Prerequisites
- App entry already exists in Play Console (you confirmed this)
- Google Play App Signing enabled (you confirmed this)
- RevenueCat account at https://app.revenuecat.com

---

## Step 1 — Create Upload Keystore

Run this **on your own machine**:
```bash
chmod +x scripts/create-upload-keystore.sh
./scripts/create-upload-keystore.sh
```
This generates `keystore/upload-key.jks`. Back it up securely — losing it means you cannot update the app.

---

## Step 2 — Add Android Platform

```bash
npm install
npm run build
npx cap add android
./scripts/configure-android-signing.sh   # injects signing into build.gradle
npx cap sync android
```

---

## Step 3 — Set Up Subscription in Play Console

1. Play Console → your app → **Monetize → Subscriptions → Create subscription**
2. Product ID: `premium_monthly`
3. Name: "Premium Plan"
4. Description: "Full 12-month meal library, portion scaling, and batch-prep mode"
5. Base plan: Monthly, auto-renewing
6. Price: **$9.99 / month USD** (Play auto-converts for other countries)
7. Add a 7-day free trial (recommended for conversion)
8. Save and **Activate** the base plan

---

## Step 4 — Set Up RevenueCat

1. Create project at https://app.revenuecat.com
2. Add Android app → paste your app package ID (`com.poordude.budgetmeal`)
3. Connect to Google Play: follow RevenueCat's service account guide
4. Create **Entitlement**: identifier = `premium`
5. Create **Product**: identifier = `premium_monthly` → attach to Play product
6. Create **Offering**: identifier = `default` → add `premium_monthly` as a package
7. Copy your **Android public API key** (starts with `goog_`)
8. Add to `.env`: `VITE_REVENUECAT_GOOGLE_API_KEY=goog_xxxxx`

---

## Step 5 — Build & Upload

```bash
cd android
./gradlew bundleRelease
```
AAB will be at `android/app/build/outputs/bundle/release/app-release.aab`

Upload to **Internal testing** track first. Add yourself as a tester.
Test subscription purchase using a [Google Play license test account](https://developer.android.com/google/play/billing/test).

---

## Step 6 — App Content Requirements (before Production)

Before promoting to production, complete in Play Console:
- **App content → Privacy Policy**: `https://budgetmealplatform.com/privacy-policy.html`
- **Data Safety**: use `docs/DATA_SAFETY.md` as reference
- **Target audience**: 18+ (food/shopping app)
- **Content rating**: complete the questionnaire (expect "Everyone")

---

## Step 7 — Go Live

Internal → Closed testing → Open testing → Production.
Recommended: spend 1-2 weeks on internal testing before expanding.
