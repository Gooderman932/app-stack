#!/usr/bin/env bash
# Run AFTER `npx cap add android`. Injects the release signing config into
# android/app/build.gradle and sets the versionCode/versionName + applicationId.
set -euo pipefail

GRADLE="android/app/build.gradle"
[ -f "$GRADLE" ] || { echo "Run 'npx cap add android' first ($GRADLE not found)."; exit 1; }

if grep -q "signingConfigs" "$GRADLE"; then
  echo "Signing config already present — skipping."
  exit 0
fi

# Insert the contents of android-signing/signing.gradle before the final closing brace
# of the android { } block is non-trivial via sed; instead we apply it via a Gradle
# 'apply from' include, which is clean and idempotent.
cp android-signing/signing.gradle android/app/signing.gradle
printf '\napply from: "signing.gradle"\n' >> "$GRADLE"

echo ">> Injected signing config (apply from: signing.gradle)."
echo ">> Remember to place keystore.properties in android/ and upload.keystore at project root."
