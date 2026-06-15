#!/usr/bin/env bash
# Creates your UPLOAD keystore (used to sign AABs before upload).
# With Google Play App Signing enabled, Google holds the real app key;
# this upload key only authorizes uploads. Keep it safe but it is recoverable
# (you can reset an upload key in Play Console if lost — unlike the app key).
set -euo pipefail

KEYSTORE="upload.keystore"
ALIAS="upload"

if [ -f "$KEYSTORE" ]; then
  echo "$KEYSTORE already exists — refusing to overwrite."
  exit 1
fi

echo ">> Creating $KEYSTORE (you'll be asked for passwords + a name/org)."
keytool -genkeypair -v \
  -keystore "$KEYSTORE" \
  -alias "$ALIAS" \
  -keyalg RSA -keysize 2048 -validity 10000

echo ""
echo ">> Done. Next:"
echo "   1. Copy android-signing/keystore.properties.example -> android/keystore.properties"
echo "   2. Fill in the passwords you just set."
echo "   3. NEVER commit upload.keystore or keystore.properties (already gitignored)."
echo "   4. For CI, base64 the keystore:  base64 -w0 upload.keystore  -> store as ANDROID_KEYSTORE_BASE64 secret."
