"""Server-authoritative quota reservations and entitlement management.

Provides:
- Atomic reservation, commit, and release to prevent race-driven overspending
- Per-user and per-feature periods (daily for rate-limited tasks, monthly for billing periods)
- Idempotency key support for reliable retries
- Operator hard spending cap enforcement
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import (
    limits_for_user,
    productivity_entitlements,
)
from database.models.billing import QuotaReservationRecord, UsageRecord
from database.models.user import User

DEFAULT_RESERVATION_TIMEOUT_SECONDS = 300  # 5 minutes
HARD_USER_SPENDING_CEILING_USD = 15.00  # Operator alert and safety clamp


@dataclass(slots=True)
class QuotaReservationResult:
    allowed: bool
    reservation_token: str | None
    feature: str
    units_requested: int
    units_remaining: int
    limit: int
    reset_at: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reservation_token": self.reservation_token,
            "feature": self.feature,
            "units_requested": self.units_requested,
            "units_remaining": self.units_remaining,
            "limit": self.limit,
            "reset_at": self.reset_at,
            "reason": self.reason,
        }


class QuotaService:
    """Manages atomic quota reservations and usage limits."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def get_period_key(feature: str, dt: datetime | None = None) -> tuple[str, datetime]:
        """Return the period key and the reset datetime for a feature.
        
        Daily reset for copilot runs and hunts; monthly reset for token budgets and digests.
        """
        now = dt or datetime.now(timezone.utc)
        if feature in ("copilot_run", "daily_hunts", "search_call"):
            key = now.strftime("%Y-%m-%d")
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return key, tomorrow
        else:
            key = now.strftime("%Y-%m")
            # Next month 1st
            year = now.year + 1 if now.month == 12 else now.year
            month = 1 if now.month == 12 else now.month + 1
            next_month = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
            return key, next_month

    @staticmethod
    def get_feature_limit(user: User, feature: str) -> int:
        """Fetch the server-authoritative limit for a feature based on user plan."""
        prod = productivity_entitlements(user)
        plan_limits = limits_for_user(user)

        if feature == "copilot_run":
            return prod["copilot_runs_per_day"]
        elif feature == "token_budget":
            return prod["copilot_token_budget"]
        elif feature == "search_call" or feature == "daily_hunts":
            return plan_limits.daily_scrape_runs
        elif feature == "max_digest":
            return plan_limits.max_digest
        return 1000  # Fallback ceiling

    async def reserve_quota(
        self,
        user: User,
        feature: str,
        units: int = 1,
        idempotency_key: str | None = None,
        workspace_id: str | None = None,
        timeout_seconds: int = DEFAULT_RESERVATION_TIMEOUT_SECONDS,
    ) -> QuotaReservationResult:
        """Atomically reserve units against plan quota with retry idempotency."""
        now = datetime.now(timezone.utc)
        period_key, reset_at = self.get_period_key(feature, now)
        limit = self.get_feature_limit(user, feature)

        # 1. Idempotency check
        if idempotency_key:
            stmt = select(QuotaReservationRecord).where(
                QuotaReservationRecord.user_id == user.id,
                QuotaReservationRecord.idempotency_key == idempotency_key,
                QuotaReservationRecord.feature == feature,
            )
            res = await self.session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                if existing.status in ("reserved", "committed"):
                    return QuotaReservationResult(
                        allowed=True,
                        reservation_token=existing.reservation_token,
                        feature=feature,
                        units_requested=existing.units_reserved,
                        units_remaining=max(0, limit - existing.units_reserved),
                        limit=limit,
                        reset_at=reset_at.isoformat(),
                    )

        # 2. Hard spending cap check (operator safeguard)
        if not await self.check_spending_cap(user.id):
            return QuotaReservationResult(
                allowed=False,
                reservation_token=None,
                feature=feature,
                units_requested=units,
                units_remaining=0,
                limit=limit,
                reset_at=reset_at.isoformat(),
                reason="Hard account spending ceiling reached. Contact support to raise limits.",
            )

        # 3. Aggregate already committed usage in this period
        stmt_usage = select(UsageRecord).where(
            UsageRecord.user_id == user.id,
            UsageRecord.feature == feature,
            UsageRecord.period_key == period_key,
        )
        res_usage = await self.session.execute(stmt_usage)
        usage_rec = res_usage.scalar_one_or_none()
        committed_units = usage_rec.units_used if usage_rec else 0

        # 4. Aggregate active unexpired reservations
        stmt_active_res = select(func.coalesce(func.sum(QuotaReservationRecord.units_reserved), 0)).where(
            QuotaReservationRecord.user_id == user.id,
            QuotaReservationRecord.feature == feature,
            QuotaReservationRecord.status == "reserved",
            QuotaReservationRecord.expires_at > now,
        )
        res_active = await self.session.execute(stmt_active_res)
        active_reserved_units = int(res_active.scalar() or 0)

        total_projected = committed_units + active_reserved_units + units
        if total_projected > limit:
            remaining = max(0, limit - (committed_units + active_reserved_units))
            return QuotaReservationResult(
                allowed=False,
                reservation_token=None,
                feature=feature,
                units_requested=units,
                units_remaining=remaining,
                limit=limit,
                reset_at=reset_at.isoformat(),
                reason=f"Quota exceeded for {feature}. Limit is {limit} per period. {remaining} units remaining.",
            )

        # 5. Create atomic reservation
        token = f"res_{uuid4().hex}"
        reservation = QuotaReservationRecord(
            reservation_token=token,
            user_id=user.id,
            workspace_id=workspace_id,
            feature=feature,
            units_reserved=units,
            units_committed=0,
            status="reserved",
            idempotency_key=idempotency_key,
            expires_at=now + timedelta(seconds=timeout_seconds),
            created_at=now,
            updated_at=now,
        )
        self.session.add(reservation)
        await self.session.commit()

        remaining_after = max(0, limit - total_projected)
        return QuotaReservationResult(
            allowed=True,
            reservation_token=token,
            feature=feature,
            units_requested=units,
            units_remaining=remaining_after,
            limit=limit,
            reset_at=reset_at.isoformat(),
        )

    async def commit_quota(
        self,
        reservation_token: str,
        units_used: int | None = None,
        cost_estimate_usd: float = 0.0,
    ) -> bool:
        """Commit reserved quota with actual consumed units, releasing any remainder."""
        now = datetime.now(timezone.utc)
        stmt = select(QuotaReservationRecord).where(
            QuotaReservationRecord.reservation_token == reservation_token
        )
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record or record.status != "reserved":
            return False

        final_units = units_used if units_used is not None else record.units_reserved
        record.status = "committed"
        record.units_committed = final_units
        record.updated_at = now

        period_key, _ = self.get_period_key(record.feature, record.created_at)

        # Update or create UsageRecord
        stmt_usage = select(UsageRecord).where(
            UsageRecord.user_id == record.user_id,
            UsageRecord.feature == record.feature,
            UsageRecord.period_key == period_key,
        )
        usage_res = await self.session.execute(stmt_usage)
        usage_rec = usage_res.scalar_one_or_none()
        if not usage_rec:
            usage_rec = UsageRecord(
                user_id=record.user_id,
                feature=record.feature,
                period_key=period_key,
                units_used=final_units,
                cost_estimate_usd=cost_estimate_usd,
                created_at=now,
                updated_at=now,
            )
            self.session.add(usage_rec)
        else:
            usage_rec.units_used += final_units
            usage_rec.cost_estimate_usd += cost_estimate_usd
            usage_rec.updated_at = now

        await self.session.commit()
        return True

    async def release_quota(self, reservation_token: str) -> bool:
        """Release unused reservation (e.g. aborted or failed execution)."""
        now = datetime.now(timezone.utc)
        stmt = select(QuotaReservationRecord).where(
            QuotaReservationRecord.reservation_token == reservation_token
        )
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record or record.status != "reserved":
            return False

        record.status = "released"
        record.updated_at = now
        await self.session.commit()
        return True

    async def get_user_usage_and_limits(self, user: User) -> dict[str, Any]:
        """Fetch all feature usages, limits, and reset times for an authenticated user."""
        now = datetime.now(timezone.utc)
        features = ["copilot_run", "token_budget", "search_call"]
        usage_data: dict[str, Any] = {}

        for feat in features:
            period_key, reset_at = self.get_period_key(feat, now)
            limit = self.get_feature_limit(user, feat)

            stmt = select(UsageRecord).where(
                UsageRecord.user_id == user.id,
                UsageRecord.feature == feat,
                UsageRecord.period_key == period_key,
            )
            res = await self.session.execute(stmt)
            rec = res.scalar_one_or_none()
            units_used = rec.units_used if rec else 0

            # Active pending
            stmt_res = select(func.coalesce(func.sum(QuotaReservationRecord.units_reserved), 0)).where(
                QuotaReservationRecord.user_id == user.id,
                QuotaReservationRecord.feature == feat,
                QuotaReservationRecord.status == "reserved",
                QuotaReservationRecord.expires_at > now,
            )
            res_active = await self.session.execute(stmt_res)
            pending = int(res_active.scalar() or 0)

            remaining = max(0, limit - (units_used + pending))
            pct_used = round(((units_used + pending) / limit) * 100.0, 1) if limit > 0 else 0.0

            usage_data[feat] = {
                "units_used": units_used,
                "units_pending": pending,
                "units_remaining": remaining,
                "limit": limit,
                "pct_used": pct_used,
                "period_key": period_key,
                "reset_at": reset_at.isoformat(),
            }

        return {
            "user_id": user.id,
            "plan": user.plan,
            "subscription_status": user.subscription_status,
            "features": usage_data,
        }

    async def check_spending_cap(
        self, user_id: str, hard_cap_usd: float = HARD_USER_SPENDING_CEILING_USD
    ) -> bool:
        """Check whether user's cumulative direct API cost in the current month exceeds safety cap."""
        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")

        stmt = select(func.coalesce(func.sum(UsageRecord.cost_estimate_usd), 0.0)).where(
            UsageRecord.user_id == user_id,
            UsageRecord.period_key.like(f"{month_key}%"),
        )
        res = await self.session.execute(stmt)
        total_cost = float(res.scalar() or 0.0)
        return total_cost < hard_cap_usd
