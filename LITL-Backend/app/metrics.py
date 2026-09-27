def metric(numerator, denominator):
    return {
        "numerator": numerator, "denominator": denominator,
        "percentage": round(numerator * 100 / denominator, 1) if denominator else None,
    }


def metrics(findings):
    total = len(findings)
    checked_identity = [f for f in findings if f.get("identity_checked")]
    checked_quotes = [f for f in findings if f.get("quote_checked")]
    checked = [f for f in findings if f.get("identity_checked") or f.get("quote_checked")]
    sources = {s["url"] for f in findings for s in f["sources"]}
    opened = {s["url"] for f in findings for s in f["sources"] if s["id"] in f.get("opened_source_ids", [])}
    return {
        "source_coverage": metric(sum(f["status"] in {"source_found", "quote_mismatch"} for f in findings), total),
        "citation_consistency": metric(sum(f["status"] == "source_found" for f in checked_identity), len(checked_identity)),
        "quotation_fidelity": metric(sum(f["status"] == "source_found" for f in checked_quotes), len(checked_quotes)),
        "review_completion": metric(sum(f["decision"] is not None for f in findings), total),
        "resolution_coverage": metric(sum(f["decision"] in {"confirmed", "corrected", "rejected"} for f in findings), total),
        "source_activity": metric(len(opened), len(sources)),
        "evidence_provenance": metric(sum(
            bool(f["sources"]) and all(all(s.get(k) for k in ("repository", "url", "retrieved_at", "locator")) for s in f["sources"])
            for f in checked
        ), len(checked)),
        "total": total, "unreviewed": sum(f["decision"] is None for f in findings),
        "unresolved": sum(f["decision"] == "unresolved" for f in findings),
        **{status: sum(f["status"] == status for f in findings) for status in (
            "ambiguous", "unavailable", "unsupported", "not_found", "not_checked", "quote_mismatch",
        )},
        "assessment": assessment_metrics(findings),
    }


def assessment_metrics(findings):
    cases = [f for f in findings if f["kind"] == "case_citation"]
    quotes = [f for f in findings if f["kind"] == "quotation"]
    assessed = [
        f for f in cases if f.get("identity_checked") and (
            f.get("identity_assessment") in {"matched", "not_matched"}
            or ("identity_assessment" not in f and f["status"] == "source_found")
        )
    ]
    located = [f for f in assessed if f["status"] == "source_found"]
    compared = [f for f in quotes if f.get("quote_checked") and f["status"] in {"source_found", "quote_mismatch"}]
    wording = [f for f in compared if f["status"] == "source_found"]
    reviewed = [f for f in findings if f["decision"] is not None]
    disposed = [f for f in findings if f["decision"] in {"confirmed", "corrected", "rejected"}]
    checks = assessed + compared
    provenance = [f for f in checks if f["sources"] and all(
        all(source.get(key) for key in ("url", "repository", "retrieved_at", "locator", "passage", "content_sha256"))
        for source in f["sources"]
    )]
    unique = {" ".join(f["label"].split()).casefold() for f in cases}
    unique_located = {" ".join(f["label"].split()).casefold() for f in located}
    definitions = {
        "identity_coverage": (len(assessed), len(cases), "Identity assessment coverage", "|A| / |C|",
            "Conclusive bounded-candidate comparisons / processed case references. Ambiguous or missing evidence is excluded from A."),
        "identity_match": (len(located), len(assessed), "Identity match among assessed", "|R| / |A|",
            "Matching identities / conclusive comparisons. This is not accuracy; no match in examined candidates does not prove invalidity."),
        "located_case_coverage": (len(located), len(cases), "Located-case coverage", "|R| / |C|",
            "Case references with a uniquely located source / processed case references. Does not establish proposition support."),
        "unique_case_coverage": (len(unique_located), len(unique), "Distinct-reference coverage", "|R_U| / |U|",
            "Distinct case labels located at least once / distinct case labels. Only whitespace and case are normalized; aliases are not merged."),
        "quote_comparison_coverage": (len(compared), len(quotes), "Quote comparison coverage", "|K| / |Q|",
            "Quotations compared against full retrieved text / processed quotations. Nearby-case attribution remains provisional."),
        "wording_match": (len(wording), len(compared), "Wording-match rate", "|W| / |K|",
            "Normalized wording matches / quotations actually compared. Not contextual correctness or verified attribution."),
        "review_completion": (len(reviewed), len(findings), "Review completion", "|H| / |N|",
            "Items with a saved human decision / processed findings. An unresolved decision counts as reviewed."),
        "review_disposition": (len(disposed), len(findings), "Review disposition", "|Z| / |N|",
            "Confirmed, corrected or rejected / processed findings. Rejection is a disposition, not verification."),
        "provenance_completeness": (len(provenance), len(checks), "Evidence provenance", "|P| / |A union K|",
            "Assessed items with URL, repository, timestamp, locator, passage and content hash / assessed case and quote items."),
    }
    return {
        "definition_version": "evidence-2",
        "counts": {
            "processed": len(findings), "case_citations": len(cases), "distinct_case_labels": len(unique),
            "statutory_references": sum(f["kind"] == "statutory_reference" for f in findings),
            "quotations": len(quotes), "assessed_identities": len(assessed), "located_cases": len(located),
            "compared_quotes": len(compared), "wording_matches": len(wording),
            "reviewed": len(reviewed), "disposed": len(disposed),
            "unreviewed": len(findings) - len(reviewed),
            "unresolved": sum(f["decision"] == "unresolved" for f in findings),
        },
        "metrics": {
            key: {
                **metric(n, d), "label": label, "formula": formula,
                "description": description, "definition_version": "evidence-2",
            }
            for key, (n, d, label, formula, description) in definitions.items()
        },
    }


def report_overview(assessment):
    c = assessment["counts"]
    if not c["processed"]:
        state, title = "no_detections", "No findings to assess"
        text = "No references were processed. This does not establish that the document contains no references or is legally correct."
    else:
        state, title = (
            ("review_incomplete", "Human review incomplete") if c["unreviewed"] else
            ("reviewed_with_unresolved", "Reviewed with unresolved items") if c["unresolved"] else
            ("reviewed", "Processed findings reviewed")
        )
        text = (
            f"{c['reviewed']} of {c['processed']} processed findings have a saved human decision; "
            f"{c['disposed']} are confirmed, corrected or rejected. "
            f"{c['located_cases']} of {c['case_citations']} case references have a located source. "
            "These counts do not certify legal correctness or all references in the original document."
        )
    attention = [
        {"label": label, "count": count} for label, count in (
            ("Statutory references requiring official-text and version checks", c["statutory_references"]),
            ("Case references without a uniquely located source", c["case_citations"] - c["located_cases"]),
            ("Quotations not compared", c["quotations"] - c["compared_quotes"]),
            ("Quotations whose wording was not found", c["compared_quotes"] - c["wording_matches"]),
            ("Findings without a conclusive human disposition", c["processed"] - c["disposed"]),
        ) if count
    ]
    return {"state": state, "title": title, "text": text, "attention": attention, "method": "deterministic-counts-1"}
