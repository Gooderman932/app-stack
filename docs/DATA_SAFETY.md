# Google Play Data Safety Declaration
## Budget Meal Platform — Poor Dude Holdings LLC

Use this as the source of truth when filling out the Play Console Data Safety section.

---

## Does your app collect or share user data?
**Yes**

---

## Data Types Collected

| Category | Data Type | Collected | Shared | Required/Optional | Purpose |
|---|---|---|---|---|---|
| Personal info | Email address | Yes | No | Required | Account creation, auth |
| Personal info | Name | Yes | No | Optional | Display name |
| Location | Approximate location (zip code) | Yes | No | Optional | Fresh Box eligibility gate |
| Financial info | Purchase history | Yes (via RevenueCat) | No | Required | Subscription management |
| App activity | App interactions | Yes | No | Required | Personalization, bug fixes |
| App activity | In-app search history | No | — | — | — |

---

## Data Sharing
- **No user data is sold to third parties.**
- Data is shared with service providers only (Supabase, RevenueCat, Stripe) strictly for app functionality.
- These providers are contractually prohibited from using the data for other purposes.

---

## Security Practices
- **Data is encrypted in transit** (TLS 1.3 via Supabase)
- **Data is encrypted at rest** (Supabase/AWS RDS at-rest encryption)
- Users can request data deletion via Account screen or email

---

## Play Console Responses (copy-paste)

### "Does your app collect or share any of the required user data types?"
→ **Yes**

### "Is all of the user data collected by your app encrypted in transit?"
→ **Yes**

### "Do you provide a way for users to request that their data is deleted?"
→ **Yes** — via Account screen "Delete Account" option and email to privacy@poorduдeholdings.com

---

## Privacy Policy URL
`https://budgetmealplatform.com/privacy-policy.html`

*(Host the public/privacy-policy.html file at this URL before Play Console review)*
