# Restaurant Operating System — Executive Summary

**Prepared for:** Board of Directors / CFO Review
**Prepared by:** Malik Amin
**Date:** February 10, 2026
**Annexure:** MASTERPLAN.md (Full Technical & Strategic Roadmap)

---

## The Problem

The restaurant chain currently operates on a fragmented technology stack — separate systems for POS, accounting, delivery, customer management, and kitchen operations. The existing tech team has failed to deliver a unified solution or deploy reliably. Every day without integration means lost revenue visibility, uncontrolled food costs, zero customer intelligence, and manual accounting overhead.

## The Solution

A **single, unified Restaurant Operating System** — custom-built, cloud-deployed, fully owned by the client. Not a SaaS rental. Not an off-the-shelf product with limitations. A proprietary platform covering every operational surface of the business.

---

## Platform at a Glance

| Layer | What It Covers |
|-------|---------------|
| **Point of Sale** | Dine-In (floor map + table management), Takeaway (token system), Call Center (phone lookup + history), Foodpanda (auto-ingest), Online Ordering (branded portal, zero commission), QR Table Ordering (scan & order from phone) |
| **Kitchen Intelligence** | Kitchen Display System (per-station ticket routing), Bill of Materials (recipe-level ingredient tracking), Stock Reconciliation (theoretical vs actual usage, variance alerts), Demand Forecasting (AI-predicted prep sheets) |
| **Financial Control** | QuickBooks Integration (Online + Desktop, bidirectional sync), FBR/PRA Tax Compliance (fiscal invoicing, QR receipts), Vendor Portal (PO workflow, 3-way matching, ledgers, self-service), Payment Processing (cash, card, wallet, split, refund, cash drawer) |
| **Customer Engine** | CRM — full Customer 360 (order history, preferences, lifetime value, segmentation), Loyalty & Rewards (points, tiers, birthday rewards, referrals), Feedback & Review Management (auto-survey, sentiment analysis, Google Review funneling) |
| **AI & Automation** | AI Copilot (natural language reporting via Claude API — "How did Friday compare to last week?"), ElevenLabs Voice Agent (Urdu/English phone ordering without human staff), Dynamic Pricing & Promotions (rules-based, auto-triggered happy hours, combos, surge pricing), Anomaly Detection (void spikes, unusual patterns, cost overruns) |
| **Communication** | WhatsApp Business API (order confirmation, tracking, bot ordering, marketing broadcasts), Digital Menu Boards (TV screens synced with POS, real-time pricing), Customer-Facing Display (second-screen order confirmation + upsell), Media Library (centralized promos, auto-resize, cross-location distribution) |
| **Enterprise & Scale** | Franchise Management (HQ command center, menu/pricing control, royalty calculation, location benchmarking), Mobile Owner App (real-time KPIs, push alerts, AI chat, remote approvals), Employee Scheduling & Attendance (shift planning, clock-in/out, overtime, payroll export), Multi-Location Dashboard (consolidated view across all branches) |

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Database tables | ~75 |
| API endpoints | 200+ |
| Frontend screens | 40+ |
| External integrations | 12 (QuickBooks, FBR, PRA, Foodpanda, WhatsApp, ElevenLabs, Claude AI, Google Maps, Weather API, Payment Gateway, SMS, Email) |
| Deployment | AWS ECS Fargate — Bahrain region (closest to Pakistan) |
| Estimated production infra cost | Rs.60,000-90,000/month (single location) |
| Per additional location | +Rs.7,500-15,000/month (shared infrastructure) |

---

## Rollout Waves

| Wave | Timeline | Deliverables | Business Impact |
|------|----------|-------------|-----------------|
| **1 — Core Completion** | Weeks 1-8 | KDS, Payments, Call Center, Reports, Production Hardening | **Go-live ready.** Restaurant can operate fully on the new system. |
| **2 — Financial Integration** | Weeks 9-16 | QuickBooks sync, FBR/PRA tax compliance, Foodpanda integration, CRM foundation | **Accounting automated.** Tax compliant. Third-party orders unified. |
| **3 — Customer Experience** | Weeks 17-24 | WhatsApp ordering + bot, Loyalty program, QR table ordering, Branded online ordering portal | **Revenue growth.** Direct orders eliminate 25-30% aggregator commission. Repeat visits increase. |
| **4 — Intelligence** | Weeks 25-30 | AI Copilot, Demand forecasting, Dynamic pricing & promotions | **Smarter operations.** Data-driven decisions. Reduced waste. Optimized pricing. |
| **5 — Supply Chain** | Weeks 31-38 | Bill of Materials, Stock reconciliation, Vendor portal & procurement | **Cost control.** 5-15% food cost savings. Vendor accountability. Purchase automation. |
| **6 — Scale & Expand** | Weeks 39-48 | Delivery fleet + GPS, Voice agent, Mobile owner app, Reservations, Digital menu boards, Franchise management | **Multi-location ready.** Fully autonomous operations. Franchise-scalable. |

**Total timeline: 12 months from prototype approval to full platform.**

---

## Competitive Advantage

| Capability | Toast / Square / Clover | Our Platform |
|-----------|------------------------|-------------|
| Monthly licensing fees | $70-150/terminal/month forever | One-time build + low hosting |
| Payment processor lock-in | Forced (their processor, their rates) | Use any processor |
| QuickBooks integration | Paid add-on, basic | Deep, bidirectional, included |
| AI-powered insights | None | Claude API — natural language reporting, anomaly detection |
| Voice ordering (Urdu) | Not available | ElevenLabs — takes orders in Urdu/English |
| WhatsApp commerce | Not available | Full ordering, tracking, marketing |
| Bill of Materials / Variance | Not available | Recipe-level tracking, cost reconciliation |
| Vendor portal | Not available | Self-service portal with ledgers, PO workflow |
| Franchise management | Basic (and expensive) | Full HQ command center, royalty engine |
| Source code ownership | Never — you rent access | Client owns 100% of the code and data |
| Customization | None — take it or leave it | Built around YOUR workflow |

---

## Investment Summary

| Component | Description |
|-----------|-------------|
| **Prototype** | Phases 1-5 — COMPLETE. Functional POS with orders, menu, floor plan, dashboard, reports. |
| **Core Completion** (Wave 1) | 8 weeks — KDS, payments, call center, reports. Delivers a go-live-ready system. |
| **Full Platform** (Waves 2-6) | 40 additional weeks — all modules described above. Transforms POS into a complete restaurant operating system. |
| **Ongoing** | Hosting, support, updates, training. Priced separately on a monthly retainer. |

> Detailed technical specifications, database schemas, architecture diagrams, screen mockups, integration maps, risk register, and infrastructure cost projections are provided in the **MASTERPLAN.md** annexure.

---

*This platform is not a point-of-sale. It is the central nervous system of a restaurant chain — where every order, every rupee, every customer, every ingredient, and every employee connects into a single source of truth.*

*The prototype proves we can build. The masterplan proves we can think. The execution will prove we can deliver.*
