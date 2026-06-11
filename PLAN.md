# PLAN.md — Contact Finder

> Written for Stage A: committed before reading CLARIFICATIONS.md or writing solution code.

---

## Architecture

A batch enrichment pipeline with four sequential stages:

```
Input CSV (company_name, mailing_address)
        ↓
[Provider Fetcher]
  Queries registry, listing, enrichment providers (parallel, per company)
  Returns raw provider payloads keyed by company_name
        ↓
[Contact Resolver]
  Normalises names across sources, detects agreement / conflict,
  selects best candidate contact per company
        ↓
[Confidence Scorer]
  Computes 0–100 score using additive signal model (see Quality section)
  Sets needs_human_review flag when score < threshold
        ↓
Output (contact_name, contact_role, contact_email_or_phone,
        confidence_score, source, needs_human_review)
```

At the scale described (~1 000 accounts) a synchronous pass over the CSV is fine. For ongoing enrichment I would put each company on a job queue (Redis/SQS), run async workers, and persist intermediate state to a table so partial failures are recoverable without re-querying all providers.

---

## Sources & strategy

I would combine three tiers, ordered by identity authority:

| Tier | Example type | Strength | Failure mode |
|------|-------------|----------|--------------|
| Business registry | State SOS filings, county clerk | Legal owner name + role, high authority | Many sole proprietors never update; some states don't publish agent details |
| Web / maps listing | Google Maps, Yelp, Bing Places equivalent | Broad coverage, often has phone | Names are display names (first-name-only, informal); role often absent |
| B2B contact enrichment | Hunter / Apollo / Clearbit equivalent | Personalised email/phone, includes self-reported confidence | Generic mailboxes (info@, sales@) are common; confidence can be over-fit to their own model |

**Strategy:** treat the registry as the identity anchor. Use the listing to corroborate the name. Use enrichment primarily for the contact channel (email/phone) and its self-reported confidence as a secondary signal only — not as the final score. Never emit a contact that cannot be traced to at least one `source_url`.

---

## Quality

### Deduplication

Normalise names before comparing: lowercase, strip common honorifics (Dr., Mr., Mrs.), map common nicknames to canonical forms (Bob→Robert, Bill→William). Two sources "agree" when their normalised names match. Two sources "conflict" when both return names that do not normalise to the same string.

### Confidence scoring (additive, 0–100)

| Signal | Points |
|--------|--------|
| Registry returns a name | +35 |
| Registry confirms a valid outreach role | +10 |
| Listing name agrees with registry (normalised) | +20 |
| Listing is the only name source | +10 |
| Name conflict across sources | −20 |
| Enrichment email is personalised | +15 |
| Generic enrichment email (info@, sales@, …) | +3 |
| Enrichment provider_confidence ≥ 80 | +15 |
| Enrichment provider_confidence 70–79 | +12 |
| Enrichment provider_confidence 60–69 | +8 |
| Enrichment provider_confidence 40–59 | +4 |
| Enrichment phone present | +3 |
| Listing phone present (non-conflict) | +2 |
| Phone confirmed by listing + enrichment | +5 |

Cap at 100. A company with zero data from any source scores 0.

**Threshold (default):** `needs_human_review = true` when `confidence_score < 60`.

### Provenance

Every output field carries the `source_url` values from which it was derived (comma-separated list in the `source` column). No value is emitted without attribution. If the only available signal is a generic email with no name, I still carry the source_url — but the confidence score reflects the weakness.

### "Cannot-verify" states

Three distinct states, all result in `needs_human_review = true`:

1. **No data** — no provider returned anything for this company. `contact_name`, `contact_email_or_phone` = null, `confidence_score` = 0.
2. **Contact method only** — phone or generic email found but no identifiable person. Emit the contact method (useful for manual outreach), set `contact_name` = null, low score.
3. **Conflict** — sources disagree on who the contact is. Emit the registry contact (higher authority) at reduced confidence, flag for human review.

### False-positive risk

The primary risk is an enrichment provider guessing a plausible email that belongs to an employee, not the AP/owner contact. Mitigation:
- require registry or listing name corroboration before scoring ≥ 60
- treat enrichment-only rows with generic emails as ≤ 30 regardless of provider_confidence

---

## Privacy / compliance

**Will do:**
- Use publicly available business registration data (SOS filings are public record in all US states)
- Use publicly listed business contact data (maps/directories, publicly crawlable)
- Use B2B enrichment providers under signed DPA, where permitted use includes collections/AR outreach
- Store only business-role contact information, not personal/residential info
- Retain `source_url` provenance for every contact so any record can be audited or removed on request

**Won't do:**
- No consumer databases — CCPA / GDPR risk from mixing consumer PII with business records
- No personal social media scraping — platform ToS violations; professional/personal boundary risk
- No purchasing contact lists without documented provenance
- No emitting personal email addresses (gmail, yahoo, hotmail) — B2B contact only
- No enriching employees who are not in an AP, financial, or ownership role
- No fabricating or interpolating contact details when sources are absent

---

## Clarifying questions

**Q1 — What is the minimum acceptable role / persona for outreach?**

*Why it matters:* "Owner" of a sole-proprietor LLC is almost certainly the right AP contact. "Receptionist" or "Technician" is not. Without a defined persona list I cannot filter the noise from enrichment providers who return any named employee.

*Default assumption:* Accept Owner, Partner, CFO, AP Manager, Office Manager, Controller. Reject Technician, Sales Rep, Customer Service, Receptionist.

*What changes depending on the answer:* A narrower list lowers recall (more rows go to human review) but improves precision. A wider list produces more automated outreach but increases the risk of contacting the wrong person. If the answer adds "anyone with signing authority" I need a more nuanced role-inference step.

---

**Q2 — What confidence threshold should trigger `needs_human_review`?**

*Why it matters:* My scoring model is heuristic with no ground truth. The threshold is the precision/recall dial. Without knowing your outreach team's capacity and the cost of a false positive (wrong contact reached), I cannot pick an optimal number.

*Default assumption:* Threshold = 60. Rows scoring < 60 are flagged for human review.

*What changes depending on the answer:* A higher threshold (e.g., 75) means the outreach team reviews more rows but fewer wrong contacts reach customers. A lower threshold (e.g., 45) means higher automation coverage but a larger share of bad contacts in the send list. If you give me a labelled sample of past enrichments I can calibrate rather than guess.

---

**Q3 — How should name conflicts across sources be handled?**

*Why it matters:* If the registry names "Tina Alvarez (Manager)" but a listing shows "Marcus Webb," I cannot resolve which person is the AP contact deterministically. This is not a data quality bug I can fix — it may mean the business changed ownership, or both people exist in different roles.

*Default assumption:* Emit the registry contact at reduced confidence with `needs_human_review = true`. Do not emit the conflicting listing name.

*What changes depending on the answer:* If the answer is "emit both candidates for human review," the output schema changes to support multiple candidate rows per company. If the answer is "trust registry over all other sources unconditionally," I can simplify the conflict branch. Either way the schema needs to be agreed before I write output parsing.
