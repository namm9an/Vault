# Vault — Live Demo Script

**Duration:** 8–10 minutes  
**URL:** http://101.53.140.68  
**Login:** naman.moudgill@e2enetworks.com / vault-demo-pass

---

## Pre-demo checklist (run 5 minutes before)

- [ ] Reset demo data: Settings → "Reset Demo Data" → "Yes, reset demo" → wait for toast
- [ ] Clear browser cache / open incognito tab
- [ ] Check http://101.53.140.68 loads in < 2 seconds
- [ ] Check Dashboard shows charts (not empty state)
- [ ] Verify notification bell shows unread count (≥ 3)
- [ ] Have this script open on second monitor or printed

---

## Act 1 — The Platform (2 min)

### Landing Page
- Open http://101.53.140.68 in a fresh incognito window
- **Say:** "This is Vault — a Ramp-inspired AI-native corporate spend platform. E2E is running the intelligence layer right here on its own GPU infrastructure."
- Scroll slowly through the landing page to show the hero, features section, and policy section
- Click **Get started free** → arrives at sign-up page
- Instead click **Sign in** (top right)

### Login
- Email: `naman.moudgill@e2enetworks.com` / Password: `vault-demo-pass`
- **Say:** "I'm logging in as Naman — the company admin."

### Dashboard
- **Say:** "The first thing you see is the spend intelligence dashboard."
- Point out the KPI cards: Total spend, MoM change, Pending approvals, Active cards
- **Say:** "Notice pending approvals — those are flagged transactions waiting for a Finance Manager to review."
- Hover over the area chart: "Four weeks of spend across the org — I can toggle between 7-day, 30-day, 90-day windows."
- Point at the pie chart: "Marketing and Travel are the biggest categories."
- Point at the bar chart: "Engineering and Marketing departments are driving most of the spend."
- Point at top merchants table: "This is live DB data, not a mockup."

---

## Act 2 — Policy Engine Live (3 min)

### Show existing flagged transactions
- Click **Transactions** in the sidebar
- **Say:** "You can see the full transaction feed. Notice the Policy column — this is the AI verdict on each transaction."
- Point out rows with FLAGGED (amber) and BLOCKED (red) in the Policy column
- Click on the **Atlassian Jira ₹22,000** row
- In the drawer, show the **Policy Result** section: "The LLM evaluated our active policies against this transaction and flagged it — quote: *'SaaS purchase above ₹10,000 requires Finance Manager approval'*."
- **Say:** "This is Llama 3.1 8B running on E2E TIR. Temperature zero — fully deterministic."
- Close the drawer

### Create a policy-triggering transaction live
- Click **+ New Transaction**
- Select card: **Carol — Ads** (Carol's marketing card)
- Merchant: **Dentsu Digital** 
- Amount: **95000**
- Category: **MARKETING**
- Click **Create Transaction**
- **Say:** "Transaction submitted. The policy engine is running right now — watch the state."
- Click on the new transaction in the list (state shows POLICY_CHECKED with spinner)
- **Say:** "The LLM is evaluating this against our policies. Let's wait..."
- After ~5-10 seconds, refresh drawer — state changes to FLAGGED
- **Say:** "Flagged. Policy 4 fired: *'Marketing agency payments above ₹75,000 require CFO sign-off'*. The Finance Manager gets notified instantly."

### Approve it as FM (optional, if time allows)
- **Say:** "As admin I can approve directly. In production, Felix the Finance Manager would get a notification."
- Enter reason: "CFO verbal approval obtained — Q2 campaign"
- Click **Approve**
- State transitions to CLEARED

### Show the policies
- Click **Policies** in the sidebar
- **Say:** "These policies were written in plain English — no regex, no code. The LLM interprets them at evaluation time."
- Point at the five active policies

---

## Act 3 — Spend Intelligence (3 min)

### Dashboard deep-dive
- Go back to **Dashboard**
- Click **90d** in the top-right range selector
- **Say:** "The dashboard aggregates in real-time on the backend, cached in Redis. Full 90-day view."

### Generate a digest
- Click **Digest** in the sidebar
- **Say:** "Vault generates a weekly AI spend digest every Monday at 9 AM. I can also trigger it manually."
- Click **Generate Digest**
- **Say:** "The LLM is summarising the past week of spend data — categories, top vendors, anomalies, recommendations. This runs on E2E TIR."
- Wait 10–15 seconds for the digest to appear in the list
- Click on the digest entry
- **Say:** "Read the headline and first recommendation aloud."
- Point at top recommendations: "Specific, actionable — not generic advice."

### Notifications
- Click the **bell icon** (top of sidebar) or **Notifications** link
- **Say:** "Every policy flag, budget alert, and digest ready notification lands here. In production you'd add email or Slack."

---

## Act 4 — Team Management (2 min)

### Cards
- Click **Cards** in the sidebar
- **Say:** "Six virtual cards — each with daily and monthly limits, assigned to departments."
- Click **Freeze** on one card, then immediately **Unfreeze** it
- **Say:** "Instant card controls. Any transaction on a frozen card would be declined at the policy check."

### Reimbursements
- Click **Reimbursements**
- **Say:** "Employees submit reimbursements for out-of-pocket expenses. They go through the same policy engine."
- Point at the POLICY_CHECKED status row: "This one is awaiting FM sign-off after the LLM flagged it."

### Departments
- Click **Departments**
- **Say:** "Three departments, each with a monthly budget. Marketing is close to its threshold — Vault would have fired an alert when it hit 80%."
- Point at the utilization bar for Marketing

### Settings
- Click **Settings**
- **Say:** "User management, role assignment, invite flow — all here."

---

## Closing (30 sec)

- **Say:** "What you've just seen is a working AI-native expense platform built in under a week — policy engine, spend intelligence, real LLM inference — all running on E2E Cloud infrastructure. The GPU work that makes the policy engine and digest possible is happening on E2E TIR right now. That's the story: E2E isn't just compute, it's what you build on top of it."

---

## Fallback talking points

**If the LLM is slow (> 30 seconds):**
> "The model is running on E2E TIR — our own GPU cloud. Inference time depends on queue depth. In a production deployment you'd add a warm-standby worker. The structured output schema means even a slow response is validated correctly."

**If a 500 error appears:**
> "Let me show you the policy engine from a different angle — here's a transaction that was already evaluated." Switch to an existing FLAGGED transaction and open the drawer.

**If the digest fails:**
> "The digest generation failed — this happens occasionally when the LLM returns a response that doesn't match the schema. In that case Vault stores the raw aggregated data and shows it as fallback." Point at the raw aggregated_input JSON if visible.

**If charts are empty after reset:**
> "The dashboard is Redis-cached. Let me bust the cache quickly." Open Settings → Reset Demo → confirm.

**If asked "is this production-ready?":**
> "This is a functional demo slice — the core AI pipelines, RBAC, multi-tenancy, and state machine are production patterns. What's missing for real production: real card network integration, KYC/KYB, mobile app. That's months, not weeks."
