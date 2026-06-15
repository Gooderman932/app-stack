#!/usr/bin/env bash
# One-time push of this codebase to your GitHub repo.
# Usage: run from the project root. You'll be prompted for your GitHub username
# and a Personal Access Token (PAT) with 'repo' scope as the password.
set -euo pipefail

REPO_URL="https://github.com/Gooderman932/app-stack.git"

git init
git add -A
git commit -m "Initial commit: Budget Meal Platform (Capacitor Android app)"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
echo ">> Pushing to $REPO_URL"
echo ">> When prompted for a password, paste a GitHub Personal Access Token (not your login password)."
git push -u origin main
echo ">> Done. CI will build the AAB once you add the repo secrets (see README)."
