from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.dashboard import DashboardSummary, TimeseriesPoint
from api.services.dashboard_service import get_summary, get_timeseries

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _default_dates() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(days=30), now


@router.get("/summary", response_model=DashboardSummary)
async def summary_route(
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
):
    if from_date is None or to_date is None:
        _from, _to = _default_dates()
        from_date = from_date or _from
        to_date = to_date or _to
    return await get_summary(scope, from_date, to_date)


@router.get("/timeseries", response_model=list[TimeseriesPoint])
async def timeseries_route(
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    bucket: str = Query(default="day"),
):
    if from_date is None or to_date is None:
        _from, _to = _default_dates()
        from_date = from_date or _from
        to_date = to_date or _to
    return await get_timeseries(scope, from_date, to_date, bucket)
