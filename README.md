# Contact Finder — AgentCollect Hiring Challenge

## How to run

Python 3.8+ only, no external dependencies.

```bash
python solution/main.py
# Output: output/contacts.csv
```

## What it does

Reads `data/companies.csv` (30 small-business accounts) and queries three mock providers per company to find a decision-maker contact suitable for AP outreach.

**Providers (all mocked):**
- `registry` — business-registry lookup (state SOS filings)
- `listing` — web/maps listing
- `enrichment` — email/phone enrichment with provider-reported confidence

**Output per row:** `contact_name`, `contact_role`, `contact_email_or_phone`, `confidence_score` (0–100), `source` (provenance URLs), `needs_human_review`.

## Confidence model

Additive, capped at 100. Threshold = 70 (from CLARIFICATIONS.md). Below threshold: `contact_email_or_phone` is blanked and `needs_human_review = true`.

| Signal | Points |
|--------|--------|
| Registry returns a name | +35 |
| Registry confirms a valid outreach role | +10 |
| Listing name agrees with registry (normalised) | +20 |
| Listing is the only name source | +10 |
| Name conflict across sources | −20 |
| Personalised enrichment email | +15 |
| Generic enrichment email (info@, sales@, …) | +3 |
| Enrichment provider_confidence ≥ 80 | +15 |
| Enrichment provider_confidence 70–79 | +12 |
| Enrichment provider_confidence 60–69 | +8 |
| Enrichment provider_confidence 40–59 | +4 |
| Enrichment phone present | +3 |
| Listing phone present (non-conflict) | +2 |
| Phone confirmed by both listing and enrichment | +5 |

Name normalisation handles: honorific stripping (Dr., Mr., …), parenthetical suffixes (`Jeff (manager)` → `Jeff`), common nicknames (`Bob` → `Robert`), and first-initial abbreviations (`S. Murphy` matches `Sean Murphy`).

**Registered Agent** roles are treated as legal designations, not business contacts — the name is surfaced for the human reviewer but the role bonus is withheld.

## Results summary (pre-committed output)

7 of 30 companies resolved automatically (confidence ≥ 70). 23 flagged for human review, including:

- **12** with no provider data at all (score 0 — intentional "cannot-verify" rows)
- **2** with a generic email / low-confidence single source
- **1** name conflict (Coastal Breeze: registry vs listing disagree on person)
- **1** Registered Agent in registry (Northgate HVAC) — not a valid AP contact
- **1** two-source name confirmation but no email found (Harbor Light Electric, score 67)

## Plan → build adaptation

My Stage A plan assumed a confidence threshold of 60. CLARIFICATIONS raised it to 70, which pushed Harbor Light Electric (score 67, two confirming sources, no email) into human-review — the right call given precision-over-recall guidance.

My plan had Owner as the top-priority role. CLARIFICATIONS put AP Manager first. Updated `_ROLE_PRIORITY` accordingly (AP/AP Manager = 0, Owner = 2).

My plan's treatment of "cannot-verify" as a distinct state maps directly to the 12 zero-score rows.
