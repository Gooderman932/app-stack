#!/usr/bin/env bash
# Injects release signing block into android/app/build.gradle
# Run AFTER: npx cap add android

set -euo pipefail

GRADLE_FILE="android/app/build.gradle"

if [ ! -f "$GRADLE_FILE" ]; then
  echo "Error: $GRADLE_FILE not found. Run 'npx cap add android' first."
  exit 1
fi

# Inject keystoreProperties loader and release signingConfig
python3 - <<'PYTHON'
import re

with open("android/app/build.gradle", "r") as f:
    content = f.read()

# Add keystoreProperties loader at top if not present
if "keystoreProperties" not in content:
    props_loader = '''
def keystorePropertiesFile = rootProject.file("keystore.properties")
def keystoreProperties = new Properties()
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
}

'''
    content = props_loader + content

# Add signingConfigs block if not present
if "signingConfigs" not in content:
    signing_block = '''
    signingConfigs {
        release {
            if (keystoreProperties['storeFile']) {
                storeFile file(keystoreProperties['storeFile'])
                storePassword keystoreProperties['storePassword']
                keyAlias keystoreProperties['keyAlias']
                keyPassword keystoreProperties['keyPassword']
            }
        }
    }
'''
    content = content.replace("    buildTypes {", signing_block + "    buildTypes {")

# Reference signingConfig in release buildType
content = re.sub(
    r"(release \{)",
    r"\1\n            signingConfig signingConfigs.release",
    content,
    count=1
)

with open("android/app/build.gradle", "w") as f:
    f.write(content)

print("android/app/build.gradle updated with release signing config.")
PYTHON
