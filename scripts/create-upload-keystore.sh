#!/usr/bin/env bash
set -euo pipefail

mkdir -p keystore

echo "Creating Android upload keystore..."
echo "You will be prompted for a keystore password and key password."
echo "IMPORTANT: Store these passwords somewhere safe — you need them to sign every release."
echo ""

keytool -genkey -v \
  -keystore keystore/upload-key.jks \
  -alias upload \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -dname "CN=Budget Meal Platform, OU=Poor Dude Holdings LLC, O=Poor Dude Holdings LLC, L=Wichita, ST=Kansas, C=US"

echo ""
echo "Keystore created at keystore/upload-key.jks"
echo ""
echo "Now create android/keystore.properties with:"
echo "  storeFile=../keystore/upload-key.jks"
echo "  storePassword=YOUR_KEYSTORE_PASSWORD"
echo "  keyAlias=upload"
echo "  keyPassword=YOUR_KEY_PASSWORD"
