from __future__ import annotations

import json
from pathlib import Path

import demo
from generate_data import FILES, generate

import docchrono
from docchrono import Case
from docchrono.domain import Polarity

ROOT = Path(__file__).parents[1]
DATA_DIR = ROOT / "data"


def _source_filenames(case: Case, document_id: str) -> set[str]:
    references = {reference.id: reference for reference in case.source_references}
    document = next(item for item in case.documents if item.id == document_id)
    return {references[item].filename for item in document.source_reference_ids}


def test_showcase_uses_the_published_release() -> None:
    assert docchrono.__version__ == "0.1.0"


def test_generator_matches_committed_corpus(tmp_path: Path) -> None:
    assert generate(check=True) == ()
    assert generate(data_dir=tmp_path) == ()
    assert {path.name for path in tmp_path.iterdir()} == set(FILES)
    assert generate(check=True, data_dir=tmp_path) == ()


def test_polarity_parallel_sources_and_evidence_round_trip(tmp_path: Path) -> None:
    case = Case.build(DATA_DIR, strict=True)

    assert case.report.complete
    assert len(case.documents) == 6
    assert {claim.polarity for claim in case.claims} >= {
        Polarity.AFFIRMED,
        Polarity.NEGATED,
    }
    assert any(
        claim.predicate == "AUTHORIZED" and claim.polarity == Polarity.NEGATED
        for claim in case.claims
    )

    relationship = next(item for item in case.relationships if item.type == "WORKS_FOR")
    assert len(relationship.supporting_claim_ids) == 1
    assert len(relationship.opposing_claim_ids) == 1

    claim_by_id = {claim.id: claim for claim in case.claims}
    supporting = claim_by_id[relationship.supporting_claim_ids[0]]
    opposing = claim_by_id[relationship.opposing_claim_ids[0]]
    assert supporting.polarity == Polarity.AFFIRMED
    assert opposing.polarity == Polarity.NEGATED

    supporting_span = case.evidence(supporting)[0]
    opposing_span = case.evidence(opposing)[0]
    assert _source_filenames(case, supporting_span.document_id) == {"01_invoice_approval.txt"}
    assert _source_filenames(case, opposing_span.document_id) == {"02_employment_exception.md"}

    documents = {document.id: document for document in case.documents}
    for claim in case.claims:
        spans = case.evidence(claim)
        assert spans
        for span in spans:
            document = documents[span.document_id]
            assert document.raw_text[span.raw_start : span.raw_end] == span.quote

    snapshot = case.save(tmp_path / "case.json")
    loaded = Case.load(snapshot)
    assert loaded.data == case.data
    assert loaded.evidence(supporting.id) == case.evidence(supporting)


def test_similarity_is_queued_for_review_not_auto_merged() -> None:
    case = Case.build(DATA_DIR, strict=True)
    item = next(review for review in case.review_items if review.kind == "entity_merge_candidate")
    mentions = {mention.id: mention for mention in case.mentions}
    evidence = {span.id: span for span in case.evidence_spans}

    assert sorted(mentions[target].text for target in item.target_ids) == [
        "Jordan Carmichael",
        "Jordon Carmichael",
    ]
    assert item.score is not None and case.config.review_threshold <= item.score
    assert item.score < case.config.auto_merge_threshold
    assert len(item.evidence_span_ids) == 2
    assert all(span_id in evidence for span_id in item.evidence_span_ids)
    assert (
        len(
            {
                entity.id
                for entity in case.entities
                if entity.canonical_name in {"Jordan Carmichael", "Jordon Carmichael"}
            }
        )
        == 2
    )


def test_demo_matches_the_committed_expected_report(tmp_path: Path) -> None:
    report = demo.run(DATA_DIR, tmp_path)
    expected = json.loads((ROOT / "expected_output" / "report.json").read_text(encoding="utf-8"))

    assert report == expected
    assert report["round_trip_verified"] is True
    assert (
        "does not decide which claim is true"
        in report["parallel_claim_relationship"]["interpretation"]
    )
    assert "not a compliance verdict" in report["human_review_notice"]
