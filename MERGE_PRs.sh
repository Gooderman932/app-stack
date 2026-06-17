#!/bin/bash
# Automated PR Merge Script for all Gooderman932 repositories
# Usage: ./MERGE_PRs.sh

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting automated PR merge for all repositories...${NC}\n"

# Function to merge a PR
merge_pr() {
    local repo=$1
    local pr_num=$2
    local merge_method=${3:-"squash"}
    
    echo -e "${YELLOW}Merging ${repo} PR #${pr_num}...${NC}"
    
    if gh pr merge "$pr_num" \
        --repo "Gooderman932/${repo}" \
        --"${merge_method}" \
        --auto \
        --delete-branch 2>/dev/null; then
        echo -e "${GREEN}✓ Merged ${repo} #${pr_num}${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Skipping ${repo} #${pr_num} (already merged or error)${NC}"
        return 1
    fi
}

# Define all PRs to merge
# Format: repo, pr_number, merge_method (merge/squash/rebase)
declare -a PRS=(
    # Fix PRs (high priority - dependencies for audit PRs)
    "app-stack,2,squash"
    "budget-meals-deal,1,squash"
    "esti-mate,2,squash"
    "business_database,9,squash"
    "homecare-pro-next,7,squash"
    "Lead-Pro,63,squash"
    "market-data,73,squash"
    "Jasper-County-Missouri-welfare-reform,1,squash"
    "gov-cybersecurity-suite,34,squash"
    "velvet-rack,1,squash"
    
    # Audit/Compliance PRs (depend on fixes above)
    "app-stack,3,merge"
    "budget-meals-deal,2,merge"
    "esti-mate,3,merge"
    "business_database,10,merge"
    "homecare-pro-next,8,merge"
    "Lead-Pro,64,merge"
    "market-data,74,merge"
    "Jasper-County-Missouri-welfare-reform,2,merge"
    "gov-cybersecurity-suite,35,merge"
    "velvet-rack,2,merge"
)

# Counters
MERGED=0
SKIPPED=0

echo -e "${BLUE}📋 Processing ${#PRS[@]} pull requests...${NC}\n"

# Process each PR
for pr_entry in "${PRS[@]}"; do
    IFS=',' read -r repo pr_num method <<< "$pr_entry"
    
    if merge_pr "$repo" "$pr_num" "$method"; then
        ((MERGED++))
    else
        ((SKIPPED++))
    fi
    
    # Add delay to avoid rate limiting
    sleep 2
done

echo -e "\n${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Merge Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "Merged:  ${GREEN}${MERGED}${NC}"
echo -e "Skipped: ${YELLOW}${SKIPPED}${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}\n"

# Additional PRs to review/close (stale - 16+ days old)
echo -e "${YELLOW}⚠ Stale PRs requiring manual review/closure:${NC}"
echo -e "  - homecare-pro-next #4 (16 days) - feat: medium-priority gaps"
echo -e "  - homecare-pro-next #6 (16 days) - fix: commercial readiness"
echo -e "  - app-stack #1 (37 days) - Play Store AAB build"
echo -e "  - esti-mate #1 (39 days) - Google Play billing flow"
echo -e "  - market-data #53 (4 months) - Auto-generated changes\n"

echo -e "${GREEN}Done!${NC}"
