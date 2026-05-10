#!/usr/bin/env bash
# Run this ONCE locally to generate your Play Store signing keystore.
# Keep the generated .jks file and passwords somewhere safe — you cannot
# change the key once you publish your first release.

set -euo pipefail

KEYSTORE_FILE="stackpilot-release.jks"
KEY_ALIAS="stackpilot"

echo "=== StackPilot Play Store Keystore Generator ==="
echo ""
echo "You will be prompted to set passwords for the keystore and key."
echo "Write them down — you will need them every time you build a release."
echo ""

keytool -genkey -v \
  -keystore "$KEYSTORE_FILE" \
  -alias "$KEY_ALIAS" \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -dname "CN=StackPilot, OU=Mobile, O=StackPilot, L=Unknown, S=Unknown, C=US"

echo ""
echo "✅ Keystore created: $KEYSTORE_FILE"
echo ""
echo "Now encode it as base64 to add to GitHub Secrets:"
echo ""
echo "  base64 -w 0 $KEYSTORE_FILE"
echo ""
echo "GitHub Secrets to set:"
echo "  KEYSTORE_BASE64  — output of the base64 command above"
echo "  KEY_STORE_PASSWORD — keystore password you just set"
echo "  KEY_ALIAS         — $KEY_ALIAS"
echo "  KEY_PASSWORD      — key password you just set"
