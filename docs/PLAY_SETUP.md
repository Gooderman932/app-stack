# Play Store + Billing Setup Guide

Your app entry already exists in Play Console and Play App Signing is enabled.
This guide covers: the upload key, the $9.99/mo subscription, RevenueCat wiring,
and the first upload.

---

## 1. Create your upload key (one time, on your machine)

```bash
./scripts/create-upload-keystore.sh
```

This produces `upload.keystore`. Because **Play App Signing** is on, Google holds the
real signing key; this upload key only authorizes uploads and is resettable in Play
Console if ever lost. Keep it private — it's gitignored.

Then:
```bash
cp android-signing/keystore.properties.example android/keystore.properties
# edit android/keystore.properties with the passwords you set
```

---

## 2. Generate the Android project + signing

```bash
npm install
npm run build
npx cap add android                      # creates android/
./scripts/configure-android-signing.sh   # injects release signing
npx cap sync android
```

Set the app identity in `android/app/build.gradle`:
- `applicationId "com.poordude.budgetmeal"` (must match capacitor.config.ts and your Play listing)
- `versionCode 1`, `versionName "1.0.0"` (bump versionCode for every upload)

Build the bundle:
```bash
npm run android:assemble    # -> android/app/build/outputs/bundle/release/app-release.aab
```

---

## 3. Create the subscription ($9.99/mo) in Play Console

Play Console → your app → **Monetize → Products → Subscriptions → Create subscription**

- **Product ID:** `premium_monthly`  ← must match `src/lib/billingConfig.ts`
- **Name:** Premium Meal Planning
- Add a **base plan**:
  - Base plan ID: `monthly-autorenew`
  - Type: Auto-renewing
  - Billing period: Monthly
  - Price: **$9.99 USD** (set other currencies as desired)
- Activate the base plan.

> The app reads these exact IDs from `src/lib/billingConfig.ts`. If you change an ID
> in Play Console, change it there too.

---

## 4. Wire RevenueCat (handles Play Billing for you)

1. Create an account at app.revenuecat.com and add a **Project**.
2. Add an **app**: platform Google Play, package `com.poordude.budgetmeal`.
3. Upload a **Play service-account JSON** with Android Publisher access
   (RevenueCat shows the exact steps; this lets it verify purchases server-side).
4. **Products** → import `premium_monthly:monthly-autorenew` from Play.
5. **Entitlements** → create `premium` → attach the product.
6. **Offerings** → create `default` (current) → add a package containing the product.
7. Copy the **Android API key** (`goog_…`) into your env as `VITE_REVENUECAT_ANDROID_KEY`.

These names (`premium`, `default`) match `src/lib/billingConfig.ts`.

---

## 5. First upload (internal testing)

1. Play Console → **Testing → Internal testing → Create new release**.
2. Upload `app-release.aab`.
3. Add your Google account as an internal tester.
4. To test the purchase: add yourself under **Monetization setup → License testing**
   (test purchases are not charged).
5. Install via the internal testing opt-in link, open Account → Subscribe, and confirm
   the premium portion-scaling + batch-prep features unlock.

---

## 6. Going to production

- Complete the Play **Data safety** form (this app collects email + app activity;
  data is stored in Supabase, payments handled by Google Play).
- Add a **Privacy Policy** URL (required because the app has accounts + payments).
- Fill the store listing (screenshots, description, category: Food & Drink).
- Promote the internal release to **Production** once tested.

---

## CI builds (optional, already wired)

`.github/workflows/android-build.yml` builds a signed AAB on each push to `main`.
Add these repo secrets:
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_REVENUECAT_ANDROID_KEY`, `VITE_SHOP_CHECKOUT_BASE_URL`
- `ANDROID_KEYSTORE_BASE64` = `base64 -w0 upload.keystore`
- `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` (=`upload`), `ANDROID_KEY_PASSWORD`
