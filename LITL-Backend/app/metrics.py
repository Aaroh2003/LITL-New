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
    }
