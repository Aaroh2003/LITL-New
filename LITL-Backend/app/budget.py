import hashlib
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .models import SourceBudgetRow, SourceRequestRow, now


PRICE_VERSION = "ik-2026-09-25"
PRICES_PAISE = {"search": 50, "document": 20}


def reserve_source_request(session, settings, run, owner_id, operation):
    cost = PRICES_PAISE[operation]
    day = datetime.now(timezone.utc).date().isoformat()
    owner_hash = hashlib.sha256(owner_id.encode()).hexdigest()
    scopes = (
        ("ik:account", settings.ik_budget_paise),
        (f"ik:day:{day}", settings.ik_daily_budget_paise),
        (f"ik:owner:{owner_hash}:{day}", settings.ik_owner_daily_budget_paise),
    )
    insert = sqlite_insert if session.bind.dialect.name == "sqlite" else pg_insert
    # Always acquire the account lock first to serialize cross-owner spending.
    buckets = []
    for scope, limit in scopes:
        session.execute(insert(SourceBudgetRow).values(scope=scope, reserved_paise=0).on_conflict_do_nothing())
        bucket = session.scalar(select(SourceBudgetRow).where(SourceBudgetRow.scope == scope).with_for_update())
        if bucket.reserved_paise + cost > limit:
            return False
        buckets.append(bucket)
    priced_count, run_cost = session.execute(select(
        func.count(SourceRequestRow.id), func.coalesce(func.sum(SourceRequestRow.cost_paise), 0),
    ).where(SourceRequestRow.run_id == run.id)).one()
    # Legacy runs only have request counts; bound those at the highest rate.
    run_cost += max(0, run.source_requests - priced_count) * max(PRICES_PAISE.values())
    if run_cost + cost > settings.ik_run_budget_paise:
        return False
    for bucket in buckets:
        bucket.reserved_paise += cost
    session.add(SourceRequestRow(
        run_id=run.id, operation=operation, cost_paise=cost,
        price_version=PRICE_VERSION, created_at=now(),
    ))
    return True


def source_usage(session, run):
    rows = list(session.scalars(select(SourceRequestRow).where(SourceRequestRow.run_id == run.id)))
    return {
        "currency": "INR",
        "reserved_paise": sum(row.cost_paise for row in rows),
        "priced_requests": len(rows),
        "unpriced_requests": max(0, run.source_requests - len(rows)),
        "requests_by_operation": dict(Counter(row.operation for row in rows)),
        "price_versions": sorted({row.price_version for row in rows}),
        "billing_status": "unreconciled",
    }
