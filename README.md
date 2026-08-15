# DocChrono Compliance Claims Lab

[![CI](https://github.com/docchrono/docchrono-compliance-claims/actions/workflows/ci.yml/badge.svg)](https://github.com/docchrono/docchrono-compliance-claims/actions/workflows/ci.yml)
[![DocChrono](https://img.shields.io/badge/DocChrono-0.1.0-3451b2)](https://pypi.org/project/docchrono/0.1.0/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

A runnable, evidence-first example of using
[DocChrono](https://github.com/docchrono/docchrono) to inspect affirmative and negative
claims in a small compliance corpus. Everything runs locally without an API key, cloud
LLM, or network call after installation.

The six committed documents are deterministic and entirely synthetic. The people,
organizations, invoice numbers, payment numbers, and `.test` email addresses are fictional.

## What this example proves

- Polarity is preserved: an asserted claim can be `AFFIRMED` or `NEGATED`.
- Every extracted claim can be traced back to an exact quote and source filename.
- An affirmed and a negated `WORKS_FOR` claim can coexist on one relationship as
  supporting and opposing source claims.
- Negated event claims remain inspectable as claims but do not become affirmative events in
  the chronology.
- Similar names can be placed in DocChrono's review queue instead of being automatically
  merged.
- A saved case can be loaded with its evidence links intact.

This example does **not** claim that DocChrono adjudicates contradictions or determines a
compliance outcome. It surfaces source claims for a human reviewer. “Supporting” and
“opposing” describe polarity relative to a graph relationship; they do not mean “true” and
“false.”

## Run it

DocChrono supports Python 3.11 through 3.13.

```bash
git clone https://github.com/docchrono/docchrono-compliance-claims.git
cd docchrono-compliance-claims
python -m venv .venv
```

Activate the environment on macOS/Linux:

```bash
source .venv/bin/activate
```

Or on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the exact production release and run the demo:

```bash
python -m pip install -r requirements.txt
python demo.py
```

The console result is committed at [`expected_output/console.txt`](expected_output/console.txt):

```text
DocChrono 0.1.0 compliance claims demo
Documents: 6
Claims: 10 (8 affirmed, 2 negated)
Events in chronology: 5
Relationships in graph: 16
Parallel WORKS_FOR evidence: 1 supporting, 1 opposing
Review candidates: 1
Evidence snapshot round-trip: verified
```

The command writes two local artifacts:

- `artifacts/report.json` — a readable extraction report with quotes and filenames.
- `artifacts/compliance.case.json` — the complete DocChrono case snapshot.

`artifacts/` is intentionally gitignored. A complete case snapshot preserves source-reference
paths and evidence text, so inspect your organization's data-handling requirements before
sharing one. `Case.save_sanitized()` removes full document text but retains evidence quotes;
it is a redacted export, not a full provenance-verification substitute.

Compare a fresh run with the committed expected result:

```bash
python demo.py --output-dir artifacts --check
```

## The synthetic scenario

| Document | Deliberate signal |
|---|---|
| `01_invoice_approval.txt` | An approved invoice and an affirmed employment claim |
| `02_employment_exception.md` | The same employment relationship, explicitly negated |
| `03_authorization_hold.txt` | A negated payment-authorization event claim |
| `04_payment_notice.eml` | Structured sender/recipient evidence and an affirmed payment event |
| `05_review_candidate_a.md` | An event involving “Jordan Carmichael” |
| `06_review_candidate_b.md` | An event involving similar “Jordon Carmichael” |

The last pair is intentionally similar. DocChrono `0.1.0` gives the pair a fuzzy similarity
score above the review threshold and below the automatic merge threshold. The demo reports
the candidate and leaves the two entities separate.

## Minimal DocChrono workflow

```python
from docchrono import Case

case = Case.build("data", strict=True)

print(case.report.complete)
print(len(case.claims))
print(len(case.timeline.all))
print(len(case.relationships))
```

`strict=True` makes a document failure fail the build instead of silently leaving a partial
case. For compliance-oriented processing, this is a useful default to consider.

## Inspect polarity and exact evidence

```python
from docchrono import Case
from docchrono.domain import Polarity

case = Case.build("data", strict=True)

for claim in case.claims:
    if claim.polarity == Polarity.NEGATED:
        print(claim.predicate, claim.polarity.value)
        for span in case.evidence(claim):
            print("  quote:", span.quote)
            print("  document id:", span.document_id)
```

An `EvidenceSpan` stores raw offsets as well as the quote. The integrity test in this
repository verifies the round-trip directly:

```python
documents = {document.id: document for document in case.documents}

for claim in case.claims:
    for span in case.evidence(claim):
        document = documents[span.document_id]
        assert document.raw_text[span.raw_start : span.raw_end] == span.quote
```

The report resolves each span's document to its source reference and prints the original
filename, so a reviewer can locate the record that produced it.

## Inspect parallel source claims

DocChrono derives a `WORKS_FOR` relationship because one accepted, asserted claim affirms
it. The relationship also points at the accepted, asserted claim that negates it:

```python
relationship = next(item for item in case.relationships if item.type == "WORKS_FOR")

print(relationship.supporting_claim_ids)  # affirmed source claims
print(relationship.opposing_claim_ids)  # negated source claims
```

Both IDs lead back to evidence through `case.evidence(...)`. The correct interpretation is:
the corpus contains competing source statements. A human must inspect authority, dates,
scope, policy, and surrounding context before drawing a conclusion.

## Inspect the review queue

```python
mentions = {mention.id: mention for mention in case.mentions}

for item in case.review_items:
    candidates = [mentions[target].text for target in item.target_ids]
    print(item.kind, item.score, candidates)
    print(item.reason)
```

In this corpus, `Jordan Carmichael` and `Jordon Carmichael` remain two entities. The review
item is a prompt for a decision, not proof that the names identify one person. This demo
deliberately does not auto-accept a merge.

## Save and load without losing provenance

```python
from docchrono import Case

case = Case.build("data", strict=True)
case.save("artifacts/compliance.case.json")

loaded = Case.load("artifacts/compliance.case.json")
assert loaded.data == case.data
assert loaded.evidence(case.claims[0].id) == case.evidence(case.claims[0])
```

## Regenerate or verify the corpus

[`generate_data.py`](generate_data.py) is the canonical fixture generator. It has no random
inputs, clock reads, or external dependencies.

Rewrite the fixtures from the embedded definitions:

```bash
python generate_data.py
```

Verify the committed files without changing them:

```bash
python generate_data.py --check
```

## Test it

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover the published package version, deterministic fixture generation, claim
polarity, parallel support/opposition, exact raw-offset evidence, review thresholds,
save/load equivalence, and the committed expected report. GitHub Actions repeats the full
demo and test suite on Python 3.11 and 3.13 using SHA-pinned actions.

## Using this pattern responsibly

1. Retain originals under your organization's evidence-handling policy.
2. Treat extracted items as claims made by documents, not established facts.
3. Preserve source references and quotes in downstream exports.
4. Review negation, ambiguity, identity resolution, dates, and authorization scope.
5. Record human decisions separately with rationale and reviewer identity.
6. Do not use this demonstration as legal advice or as an automated eligibility,
   disciplinary, or enforcement decision system.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
