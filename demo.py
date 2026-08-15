"""Build and explain a source-linked synthetic compliance case with DocChrono."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import docchrono
from docchrono import Case
from docchrono.domain import Claim, Polarity, SourceReference

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts"
EXPECTED_REPORT = ROOT / "expected_output" / "report.json"


def _source_lookup(
    case: Case,
) -> tuple[dict[str, SourceReference], dict[str, tuple[str, ...]]]:
    references = {reference.id: reference for reference in case.source_references}
    filenames_by_document: dict[str, tuple[str, ...]] = {}
    for document in case.documents:
        filenames_by_document[document.id] = tuple(
            sorted(references[item].filename for item in document.source_reference_ids)
        )
    return references, filenames_by_document


def _claim_evidence(case: Case, claim: Claim) -> list[dict[str, Any]]:
    _, filenames_by_document = _source_lookup(case)
    return [
        {
            "sources": list(filenames_by_document[span.document_id]),
            "quote": span.quote,
            "raw_start": span.raw_start,
            "raw_end": span.raw_end,
        }
        for span in case.evidence(claim)
    ]


def _participant_value(case: Case, claim: Claim) -> list[dict[str, str]]:
    entities = {entity.id: entity for entity in case.entities}
    values: list[dict[str, str]] = []
    for participant in claim.participants:
        if participant.entity_id is not None:
            value = entities[participant.entity_id].canonical_name
        elif participant.literal is not None:
            value = participant.literal
        elif participant.mention_id is not None:
            mention = next(item for item in case.mentions if item.id == participant.mention_id)
            value = mention.text
        else:  # pragma: no cover - DocChrono validates this invariant
            continue
        values.append({"role": participant.role, "value": value})
    return values


def _claim_record(case: Case, claim: Claim) -> dict[str, Any]:
    return {
        "predicate": claim.predicate,
        "kind": claim.kind.value,
        "polarity": claim.polarity.value,
        "modality": claim.modality.value,
        "score": claim.score,
        "participants": _participant_value(case, claim),
        "evidence": _claim_evidence(case, claim),
    }


def _claim_sort_key(record: dict[str, Any]) -> tuple[str, ...]:
    evidence = record["evidence"]
    first_source = evidence[0]["sources"][0] if evidence else ""
    first_quote = evidence[0]["quote"] if evidence else ""
    return (
        first_source,
        record["predicate"],
        record["polarity"],
        first_quote,
    )


def _review_records(case: Case) -> list[dict[str, Any]]:
    mentions = {mention.id: mention for mention in case.mentions}
    evidence = {span.id: span for span in case.evidence_spans}
    _, filenames_by_document = _source_lookup(case)
    records: list[dict[str, Any]] = []
    for item in case.review_items:
        spans = [evidence[span_id] for span_id in item.evidence_span_ids]
        records.append(
            {
                "kind": item.kind,
                "candidates": sorted(
                    mentions[target_id].text
                    for target_id in item.target_ids
                    if target_id in mentions
                ),
                "score": item.score,
                "reason": item.reason,
                "evidence": [
                    {
                        "sources": list(filenames_by_document[span.document_id]),
                        "quote": span.quote,
                    }
                    for span in spans
                ],
                "recommended_action": (
                    "Human review required; do not merge based on this score alone."
                ),
            }
        )
    return sorted(records, key=lambda record: (record["kind"], record["candidates"]))


def build_report(case: Case, *, round_trip_verified: bool) -> dict[str, Any]:
    """Create a stable, human-readable report without environment-specific IDs."""

    claim_by_id = {claim.id: claim for claim in case.claims}
    parallel = next(
        relationship
        for relationship in case.relationships
        if relationship.type == "WORKS_FOR"
        and relationship.supporting_claim_ids
        and relationship.opposing_claim_ids
    )
    supporting = sorted(
        (_claim_record(case, claim_by_id[claim_id]) for claim_id in parallel.supporting_claim_ids),
        key=_claim_sort_key,
    )
    opposing = sorted(
        (_claim_record(case, claim_by_id[claim_id]) for claim_id in parallel.opposing_claim_ids),
        key=_claim_sort_key,
    )
    all_claims = sorted((_claim_record(case, claim) for claim in case.claims), key=_claim_sort_key)
    affirmed = sum(claim.polarity == Polarity.AFFIRMED for claim in case.claims)
    negated = sum(claim.polarity == Polarity.NEGATED for claim in case.claims)

    chronology: list[dict[str, Any]] = []
    for event in case.timeline.all:
        date_values: set[str] = set()
        for temporal in event.temporal:
            value = temporal.start or temporal.end
            if temporal.resolved and value is not None:
                date_values.add(value)
        dates = sorted(date_values)
        chronology.append(
            {
                "date": dates[0] if dates else None,
                "title": event.title,
                "evidence": [
                    item
                    for claim_id in event.claim_ids
                    for item in _claim_evidence(case, claim_by_id[claim_id])
                ],
            }
        )

    return {
        "demo": "DocChrono synthetic compliance claims",
        "docchrono_version": docchrono.__version__,
        "build_complete": case.report.complete,
        "counts": {
            "documents": len(case.documents),
            "entities": len(case.entities),
            "claims": len(case.claims),
            "affirmed_claims": affirmed,
            "negated_claims": negated,
            "events": len(case.events),
            "relationships": len(case.relationships),
            "review_items": len(case.review_items),
        },
        "parallel_claim_relationship": {
            "type": parallel.type,
            "supporting_claims": supporting,
            "opposing_claims": opposing,
            "interpretation": (
                "The documents make opposing source claims about the same relationship. "
                "DocChrono preserves both; it does not decide which claim is true."
            ),
        },
        "review_queue": _review_records(case),
        "chronology": chronology,
        "claims": all_claims,
        "round_trip_verified": round_trip_verified,
        "human_review_notice": (
            "Extraction output is evidence for review, not a compliance verdict. "
            "A qualified reviewer must inspect the quoted sources, context, and applicable policy."
        ),
    }


def run(data_dir: Path, output_dir: Path) -> dict[str, Any]:
    case = Case.build(data_dir, strict=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = case.save(output_dir / "compliance.case.json")
    round_trip_verified = Case.load(snapshot_path).data == case.data
    report = build_report(case, round_trip_verified=round_trip_verified)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def render_console(report: dict[str, Any]) -> str:
    counts = report["counts"]
    parallel = report["parallel_claim_relationship"]
    lines = [
        f"DocChrono {report['docchrono_version']} compliance claims demo",
        f"Documents: {counts['documents']}",
        (
            f"Claims: {counts['claims']} "
            f"({counts['affirmed_claims']} affirmed, {counts['negated_claims']} negated)"
        ),
        f"Events in chronology: {counts['events']}",
        f"Relationships in graph: {counts['relationships']}",
        (
            f"Parallel {parallel['type']} evidence: "
            f"{len(parallel['supporting_claims'])} supporting, "
            f"{len(parallel['opposing_claims'])} opposing"
        ),
        f"Review candidates: {counts['review_items']}",
        "Evidence snapshot round-trip: verified"
        if report["round_trip_verified"]
        else "Evidence snapshot round-trip: FAILED",
        "",
        "Human review notice:",
        str(report["human_review_notice"]),
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="also compare the stable report with expected_output/report.json",
    )
    args = parser.parse_args()
    report = run(args.data, args.output_dir)
    print(render_console(report))
    if args.check:
        expected = json.loads(EXPECTED_REPORT.read_text(encoding="utf-8"))
        if report != expected:
            print("\nGenerated report differs from expected_output/report.json")
            return 1
        print("\nExpected report: matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
