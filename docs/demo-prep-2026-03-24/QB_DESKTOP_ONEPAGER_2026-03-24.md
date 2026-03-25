# QuickBooks Desktop — Discussion Guide

**For:** Younis Kamran team meeting, March 24, 2026
**Status:** Architected, not built. QB Online is the current ready path.

---

## What Is It?

QuickBooks Desktop is a separate integration track that connects the POS to a locally-installed QuickBooks application (Pro, Premier, or Enterprise) running on the client's PC or server.

It uses a different sync model than QB Online:

| | QB Online (Built) | QB Desktop (Planned) |
|---|---|---|
| **Connection** | OAuth via browser | Web Connector app on client PC |
| **Protocol** | REST API (JSON) | SOAP/XML polling |
| **Sync timing** | Near real-time | Every 15 minutes (batch) |
| **Requirement** | Internet + QB subscription | QB Desktop running on a PC |
| **Our status** | Production ready | Needs ~4 weeks to build |

---

## Why It's a Separate Track

QB Desktop is not a configuration change on top of QB Online. The underlying technology is fundamentally different:

- **Online** = we push data to Intuit's cloud via REST API
- **Desktop** = a small Windows app (Web Connector) polls our server and shuttles data to/from the local QB file via XML

The POS business logic (what gets posted, how accounts map, what the audit trail looks like) stays the same. The transport layer is entirely different.

---

## What Carries Over from QB Online

These are already built and will be reused:

- POS accounting concepts (25 account needs — income, COGS, tax, bank, etc.)
- Account matching algorithm (fuzzy match POS needs to QB accounts)
- Sync queue with retry logic
- Audit trail and sync logging
- Admin UI (mappings, health check, diagnostics)
- Entity mapping (track what's been synced)

---

## What Needs to Be Built

| Component | Effort | Description |
|-----------|--------|-------------|
| Web Connector endpoint | ~1 week | SOAP server that speaks QBWC protocol |
| XML request builders | ~1.5 weeks | Build QBXML for SalesReceipts, CreditMemos, JournalEntries, etc. |
| XML response parsers | ~3 days | Parse QB Desktop responses, handle errors |
| Polling sync adapter | ~3 days | Pull-based queue (QBWC fetches from us) instead of push |
| Desktop connection UI | ~2 days | Replace OAuth flow with QBWC setup wizard |
| Testing | ~3 days | Unit + integration + end-to-end |
| **Total** | **~4 weeks** | |

---

## What We Need From You Before We Can Build

These questions must be answered before scoping begins:

### Critical (Must Know)

1. **Does the client actually need Desktop, or would QB Online work?**
   - Online is simpler, cheaper to maintain, already built
   - If the client is open to Online, that's the fastest path

2. **Which Desktop edition?** Pro / Premier / Enterprise
   - Each has different QBXML capabilities
   - Enterprise supports features Pro does not

3. **Which year/version?** (e.g., QB Premier 2024)
   - Year determines which XML SDK version is supported
   - Older versions have limitations

4. **Single-user or multi-user mode?**
   - Affects concurrent access and locking behavior

5. **Where is the QB company file?**
   - One PC, local file server, or remote desktop?
   - The Web Connector must run on a machine with access to the file

6. **Can a Web Connector be installed on that machine?**
   - Requires admin access to install
   - Must remain running during business hours

7. **Does that machine stay on overnight?**
   - Sync only works when the machine + QB are running

### Important (Should Know)

8. **Per-order posting or daily summary?**
   - Per-order: each SalesReceipt posted individually
   - Daily summary: one Journal Entry per day (cleaner for high-volume)

9. **Do they need voids, refunds, discounts, tax, and cash over/short in QB?**
   - Full scope vs. revenue-only posting

10. **Do they use Classes, Locations, or custom fields heavily?**
    - Affects mapping complexity

11. **Are they willing to pilot QB Online first while Desktop is built?**
    - Gets them accounting integration sooner, no waiting

---

## Recommended Talking Point

> "We can absolutely support QuickBooks Desktop. It's a separate delivery track because the integration model is fundamentally different from QB Online — polling instead of push, XML instead of JSON, local machine instead of cloud. We need the exact Desktop version and environment details first, then we can scope the adapter properly. Timeline is approximately 4 weeks from when we have those details. In the meantime, QB Online is ready today."

---

## Timeline

| Phase | Duration | Dependency |
|-------|----------|------------|
| Client provides version/environment details | 1 week | Younis team gathers info |
| Architecture review + SOW | 3 days | After details received |
| Development | 4 weeks | After SOW approved |
| Testing with client's QB file | 1 week | Client provides test file |
| Go-live | 1 day | After testing |
| **Total** | **~6 weeks end-to-end** | From info received to go-live |

---

## Key Risk

If the client's QB Desktop version is very old (pre-2020) or uses a non-standard setup, the integration may require additional compatibility work. Knowing the exact version upfront avoids surprises.
