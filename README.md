# Budget Meal Platform — Capacitor Android App

A native Android app (Capacitor + React/TypeScript) for the Kansas Budget Meal Platform:
a 12-month meal-planning library, a Kansas cottage-food pantry shop, a budget tracker,
and the Kansas Producer Network for local bulk sourcing. Backend is Supabase (Postgres + Auth + RLS).

## What's native here
- **Capacitor 7** wraps the UI in a real Android project (`android/`, Gradle, signed `.aab`).
- **Google Play Billing** for digital subscriptions via RevenueCat (`@revenuecat/purchases-capacitor`).
- **Native plugins:** App lifecycle, in-app Browser (external physical-goods checkout), Preferences.
- Physical cottage-food goods use **external checkout** (Stripe/Shopify) — required by Google Play policy,
  which forbids selling physical goods through Play Billing.

## Project layout
```
src/
  lib/         supabase client, billing (Play Billing), external checkout, types
  context/     AuthContext (Supabase auth + billing init)
  screens/     Auth, Plans, PlanDetail, Shop, Budget, Producer, ProducerSignup, Account
  components/  Nav
capacitor.config.ts   app id: com.poordude.budgetmeal
.github/workflows/    CI that builds a signed AAB
```

## Local setup
```bash
npm install
cp .env.example .env      # fill in real keys
npm run dev               # web preview at http://localhost:5173
```

## Build the Android app
```bash
npm run build             # compile web bundle into dist/
npx cap add android       # first time only — creates the android/ native project
npx cap sync android      # copy web build + plugins into android/
npx cap open android      # open in Android Studio to run / archive
```
To build a release bundle from the command line: `npm run android:assemble`
(requires a signing keystore configured in `android/app/build.gradle`).

## Environment variables
| Variable | Purpose |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable (RLS-protected) key — safe to ship |
| `VITE_REVENUECAT_ANDROID_KEY` | RevenueCat Android key (app.revenuecat.com) for Play Billing |
| `VITE_SHOP_CHECKOUT_BASE_URL` | Hosted checkout for physical goods |

## CI / CD (GitHub Actions)
`.github/workflows/android-build.yml` builds the web bundle, adds the Android platform,
and produces a signed `.aab` on every push to `main`. Add these repo secrets
(Settings → Secrets and variables → Actions):

- `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_REVENUECAT_ANDROID_KEY`, `VITE_SHOP_CHECKOUT_BASE_URL`
- `ANDROID_KEYSTORE_BASE64` (your upload keystore, base64-encoded), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`

## Pushing to GitHub
```bash
./scripts/push-to-github.sh
```
You'll authenticate with your own GitHub Personal Access Token (repo scope).

## Play Store release checklist
1. Generate an upload keystore: `keytool -genkey -v -keystore upload.keystore -alias upload -keyalg RSA -keysize 2048 -validity 10000`
2. Configure signing in `android/app/build.gradle` (read passwords from env).
3. Create the app in Google Play Console; create a subscription product; mirror it in RevenueCat.
4. Run a SHA validation / Play App Signing enrollment.
5. Upload the `.aab` (from CI artifact or `npm run android:assemble`) to an internal testing track first.

## Compliance note
The cottage-food shop only sells shelf-stable, non-TCS SKUs that are exempt under Kansas MF3138.
Ingredient classification and fulfillment routing live in the backend
(`product_classifications`, `pipeline_routing_rules`).
