# Budget Meal Platform

A native Android app (Capacitor 7) for budget meal planning, cottage food sales, and a Kansas Producer Network.

## Stack
- **Frontend**: React 18 + TypeScript + Vite
- **Native shell**: Capacitor 7 (Android)
- **Backend**: Supabase (PostgreSQL + Auth + RLS)
- **Subscriptions**: Google Play Billing via RevenueCat
- **Physical goods checkout**: External browser (Stripe/Shopify)

## App Structure

| Screen | Path | Description |
|--------|------|-------------|
| Plans | `/` | 12-month meal plan library; months 4–12 locked behind Premium |
| Plan Detail | `/plans/:id` | Recipes, ingredients, portion scaling (Premium), batch-prep (Premium) |
| Shop | `/shop` | Cottage food SKUs — ships nationwide |
| Budget | `/budget` | Full-year cost estimator vs. SNAP benchmarks |
| Producers | `/producers` | Kansas Producer Network — browse listings or apply to join |
| Fresh Box | `/fresh-box` | Phase 2 weekly/biweekly fresh delivery (Kansas zip codes only) |
| Account | `/account` | Auth, Premium upgrade, restore purchases |

## Quick Start

```bash
cp .env.example .env
# fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_REVENUECAT_GOOGLE_API_KEY

npm install
npm run build

npx cap add android
npx cap sync android
npx cap open android   # opens Android Studio
```

## First Release Build

1. Generate upload keystore: `./scripts/create-upload-keystore.sh`
2. Fill in `android/keystore.properties`
3. `./scripts/configure-android-signing.sh`
4. `cd android && ./gradlew bundleRelease`
5. Upload `android/app/build/outputs/bundle/release/app-release.aab` to Play Console

## CI/CD (GitHub Actions)

Add these secrets to your repo (Settings → Secrets and variables → Actions):

| Secret | Value |
|--------|-------|
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Your Supabase anon key |
| `VITE_REVENUECAT_GOOGLE_API_KEY` | RevenueCat Android key |
| `KEYSTORE_BASE64` | `base64 -w 0 keystore/upload-key.jks` |
| `KEYSTORE_PASSWORD` | Keystore password |
| `KEY_PASSWORD` | Key password |

Every push to `main` builds a signed AAB and uploads it as an artifact.

## Compliance

- **Product classification**: 71 ingredients classified per KDA MF3138
- **Routing engine**: 88 rules across 5 pipeline types (National Bulk, Regional Fresh, Producer Direct, Customer Self-Source, Not Eligible)
- **Privacy Policy**: `public/privacy-policy.html`
- **Terms of Service**: `public/terms.html`
- **Data Safety**: `docs/DATA_SAFETY.md`
- **Play Setup**: `docs/PLAY_SETUP.md`

## Business Structure

| Revenue Stream | Payment Rail | Geographic Scope |
|---------------|-------------|-----------------|
| Premium subscription ($9.99/mo) | Google Play Billing / RevenueCat | Nationwide |
| Cottage food SKUs | External checkout (Stripe/Shopify) | Nationwide |
| Fresh Box delivery | External checkout | Kansas only |
| Producer Network fees | TBD (Phase 2+) | Kansas |

## Proprietary IP

1. **Regulatory-Aware Supply Routing Engine** — ingredient classifications + pipeline routing rules resolve legal compliance automatically per ingredient × destination region.
2. **Budget-Optimized Meal Matching** — time-series pricing feeds + routing engine generate lowest-cost compliant shopping lists per customer per region.

Both components are candidates for provisional patent or trade secret protection.
