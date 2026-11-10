# Android release (Google Play)

The Android app is the web app (`frontend/`) wrapped with Capacitor 8.
Package name: **`com.poordudeholdings.appstack`**. It is permanent once the
first build is uploaded to Play, and the backend's Play billing checks use the
same value (`GOOGLE_PLAY_PACKAGE_NAME`).

Releases are built by the **Android release (AAB)** workflow
(`.github/workflows/android-release.yml`), which produces a signed
`app-release.aab` to upload to Play Console.

## One-time setup

1. **Upload key.** On your own machine, with a JDK installed:

   ```bash
   bash scripts/generate-upload-keystore.sh
   ```

   Keep the `.jks` file and its password in your password manager. With Play
   App Signing, Google holds the key users' installs are signed with; this
   upload key can be reset in Play Console if it is ever lost. Never commit it:
   `*.jks`, `*.keystore` and `*.p12` are git-ignored and CI fails if one is
   tracked.

2. **Repository secrets** (Settings → Secrets and variables → Actions → Secrets):

   | Secret | Value |
   |---|---|
   | `KEYSTORE_BASE64` | `base64 -w 0 app-stack-upload.jks` (macOS: `base64 -i app-stack-upload.jks`) |
   | `KEY_STORE_PASSWORD` | the keystore password |
   | `KEY_ALIAS` | `upload` |
   | `KEY_PASSWORD` | the same password |

3. **Repository variables** (same page → Variables). The web app is compiled
   with these values, so they must point at production:

   | Variable | Value |
   |---|---|
   | `REACT_APP_BACKEND_URL` | the live backend, `https://…` |
   | `REACT_APP_GOOGLE_CLIENT_ID` | the **web** OAuth client ID (`….apps.googleusercontent.com`), same as the backend's `GOOGLE_CLIENT_ID` |

4. **Google sign-in on Android.** In Google Cloud Console → Credentials, create
   an **Android** OAuth client for package `com.poordudeholdings.appstack` for
   each signing certificate's SHA-1: the **app signing key** (Play Console →
   Test and release → App integrity) and the **upload key**. Without it, native
   sign-in fails with `DEVELOPER_ERROR` (code 10).

5. **Play Billing.** In Play Console create the subscriptions with product IDs
   exactly **`pro`** and **`team`**: the app (`App.js`) and the backend
   (`PLAY_PRODUCT_TIERS`) use these IDs. The backend needs
   `GOOGLE_PLAY_SERVICE_ACCOUNT_FILE` pointing at a service account that Play
   Console has granted "View financial data" and "Manage orders and
   subscriptions".

## Each release

1. Actions → **Android release (AAB)** → Run workflow.
   - `version_code`: a whole number higher than every build already uploaded.
   - `version_name`: what users see, e.g. `1.0.0`.
2. The job summary shows the upload certificate's SHA-256. It must match Play
   Console → App integrity → Upload key certificate.
3. Download the `app-stack-<version>-<code>` artifact and upload the `.aab` to
   an internal testing track first.

To build locally: `cd frontend && npm ci --legacy-peer-deps && npm run build && npx cap sync android`,
then `cd android && ./gradlew bundleRelease -PVERSION_CODE=<n> -PVERSION_NAME=<x.y.z>`
(unsigned unless `ANDROID_KEYSTORE_PATH`, `KEY_STORE_PASSWORD`, `KEY_ALIAS` and
`KEY_PASSWORD` are set).

## Before the first public release

- **Icons and splash screens** are still Capacitor's placeholders
  (`frontend/android/app/src/main/res/mipmap-*`, `drawable*`). Generate real ones
  from a 1024×1024 logo with `npx @capacitor/assets generate --android`.
- **Data safety form and privacy policy.** The app no longer loads any
  third-party scripts (the Emergent badge, Emergent script and PostHog session
  recording were removed from `public/index.html`). Declare what the app itself
  collects: Google account email and name, and purchase history.

## Known follow-ups

- `@codetrix-studio/capacitor-google-auth` is unmaintained (last release
  targets Capacitor 6) and uses Google's legacy Sign-In API. A patch in
  `frontend/patches/` (applied by `npm ci`) makes it build on Capacitor 8. Plan a
  move to a maintained plugin that uses Android Credential Manager.
- Gradle reports deprecated features that Gradle 9 will remove; they come from
  plugin build files and will be addressed with the next Capacitor upgrade.
