#!/usr/bin/env bash
# Creates the Google Play *upload key* for the App Stack Android app.
# Run once, on your own machine (needs a JDK for keytool). See docs/android-release.md.
#
# With Play App Signing, Google holds the key that signs what users install.
# This key only proves uploads come from you; if it is ever lost or leaked,
# Play Console can reset it. Still: keep the file and passwords in a password
# manager, and never commit them (*.jks is git-ignored).
set -euo pipefail

KEYSTORE_FILE="${1:-app-stack-upload.jks}"
KEY_ALIAS="upload"

if [[ -e "$KEYSTORE_FILE" ]]; then
  echo "Refusing to overwrite existing $KEYSTORE_FILE" >&2
  exit 1
fi
command -v keytool >/dev/null || { echo "keytool not found: install a JDK (17 or newer)" >&2; exit 1; }

echo "Choose a long random password and store it in your password manager."
read -r -s -p "Keystore password (12+ characters): " STORE_PASS; echo
read -r -s -p "Repeat the password: " STORE_PASS_AGAIN; echo
if [[ "$STORE_PASS" != "$STORE_PASS_AGAIN" ]]; then echo "Passwords do not match" >&2; exit 1; fi
if (( ${#STORE_PASS} < 12 )); then echo "Use at least 12 characters" >&2; exit 1; fi
unset STORE_PASS_AGAIN
# Passed to keytool through the environment, never on the command line.
export STORE_PASS
echo
echo "Now your name and organisation (shown in the certificate):"

keytool -genkeypair -v \
  -storetype PKCS12 \
  -keystore "$KEYSTORE_FILE" \
  -alias "$KEY_ALIAS" \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000 \
  -storepass:env STORE_PASS \
  -keypass:env STORE_PASS

echo
echo "Created $KEYSTORE_FILE (alias: $KEY_ALIAS)."
echo
echo "Add these repository secrets (Settings > Secrets and variables > Actions):"
echo "  KEYSTORE_BASE64     output of: base64 -w 0 $KEYSTORE_FILE   (macOS: base64 -i $KEYSTORE_FILE)"
echo "  KEY_STORE_PASSWORD  the password you just chose"
echo "  KEY_ALIAS           $KEY_ALIAS"
echo "  KEY_PASSWORD        the same password (PKCS12 keys share the store password)"
echo
echo "Upload certificate fingerprint (Play Console shows the same value once you register the key):"
keytool -list -v -keystore "$KEYSTORE_FILE" -alias "$KEY_ALIAS" -storepass:env STORE_PASS | grep -E 'SHA256:' || true
unset STORE_PASS
