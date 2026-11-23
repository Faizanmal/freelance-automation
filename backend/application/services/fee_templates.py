"""Versioned platform fee templates service.

Non-marketplace presets only (marketplace boards are excluded from Signal Desk finance):
- Stripe (Direct Invoicing): 2.9% + $0.30 per successful card transaction.
- Custom: Flexible manual overrides.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.finance import FeeTemplateRecord

# Marketplace platforms are intentionally omitted from finance presets.
MARKETPLACE_FEE_PLATFORMS = frozenset({"upwork", "fiverr", "freelancer"})

# Official system fee templates (versioned with primary source links and effective dates)
SYSTEM_FEE_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "tpl_direct_stripe",
        "slug": "direct_stripe_us",
        "template_name": "Direct Client Invoicing (Stripe US)",
        "name": "Direct Client Invoicing (Stripe US)",
        "platform": "direct_stripe",
        "region": "US",
        "currency": "USD",
        "contract_service_fee_pct": 0.0,
        "contract_service_fee_fixed": 0.0,
        "fee_tax_pct": 0.0,
        "tax_on_fee_pct": 0.0,
        "withholding_tax_pct": 0.0,
        "withholding_tax_base": "gross",
        "withholding_base": "gross",
        "withdrawal_fee": 0.0,
        "withdrawal_currency": "USD",
        "processor_fee_pct": 2.9,
        "processor_charge_pct": 2.9,
        "processor_fee_fixed": 0.30,
        "processor_charge_fixed": 0.30,
        "source_url": "https://stripe.com/pricing",
        "effective_date": "2024-01-01",
        "eligibility_notes": "Direct client invoicing via Stripe credit card: 2.9% + $0.30 per successful charge. No platform commission.",
        "is_system": True,
        "is_system_template": True,
        "is_active": True,
    },
    {
        "id": "tpl_custom_manual",
        "slug": "custom_manual",
        "template_name": "Custom / Manual Rates",
        "name": "Custom / Manual Rates",
        "platform": "custom",
        "region": "GLOBAL",
        "currency": "USD",
        "contract_service_fee_pct": 0.0,
        "contract_service_fee_fixed": 0.0,
        "fee_tax_pct": 0.0,
        "tax_on_fee_pct": 0.0,
        "withholding_tax_pct": 0.0,
        "withholding_tax_base": "gross",
        "withholding_base": "gross",
        "withdrawal_fee": 0.0,
        "withdrawal_currency": "USD",
        "processor_fee_pct": 0.0,
        "processor_charge_pct": 0.0,
        "processor_fee_fixed": 0.0,
        "processor_charge_fixed": 0.0,
        "source_url": "",
        "effective_date": "2024-01-01",
        "eligibility_notes": "Fully customizable manual rates for direct contracts, wires, or negotiated agreements.",
        "is_system": True,
        "is_system_template": True,
        "is_active": True,
    },
]


class FeeTemplateService:
    """Manages platform fee templates and user overrides."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def get_system_templates() -> list[dict[str, Any]]:
        """Return non-marketplace system fee templates."""
        return [
            dict(t)
            for t in SYSTEM_FEE_TEMPLATES
            if str(t.get("platform") or "").lower() not in MARKETPLACE_FEE_PLATFORMS
        ]

    async def list_templates(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List system templates combined with active user-specific templates."""
        results: list[dict[str, Any]] = self.get_system_templates()

        if user_id:
            stmt = select(FeeTemplateRecord).where(
                FeeTemplateRecord.user_id == user_id,
            ).order_by(FeeTemplateRecord.created_at.desc())
            res = await self.session.execute(stmt)
            for record in res.scalars().all():
                results.append({
                    "id": f"tpl_{record.id}",
                    "slug": record.slug,
                    "template_name": record.name,
                    "name": record.name,
                    "platform": record.platform,
                    "region": record.region,
                    "currency": record.withdrawal_currency,
                    "contract_service_fee_pct": record.contract_service_fee_pct,
                    "contract_service_fee_fixed": record.contract_service_fee_fixed,
                    "fee_tax_pct": record.tax_on_fee_pct,
                    "tax_on_fee_pct": record.tax_on_fee_pct,
                    "withholding_tax_pct": record.withholding_tax_pct,
                    "withholding_tax_base": record.withholding_base,
                    "withholding_base": record.withholding_base,
                    "withdrawal_fee": record.withdrawal_fee,
                    "withdrawal_currency": record.withdrawal_currency,
                    "processor_fee_pct": record.processor_charge_pct,
                    "processor_charge_pct": record.processor_charge_pct,
                    "processor_fee_fixed": record.processor_charge_fixed,
                    "processor_charge_fixed": record.processor_charge_fixed,
                    "source_url": record.source_url,
                    "effective_date": record.effective_date,
                    "eligibility_notes": record.eligibility_notes,
                    "is_system": False,
                    "is_system_template": False,
                    "is_active": True,
                })
        return results

    async def get_template_by_id(
        self, template_id: str | int, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Find template by ID or slug (system template or user template)."""
        tpl_str = str(template_id)
        for tpl in SYSTEM_FEE_TEMPLATES:
            if str(tpl["id"]) == tpl_str or tpl["slug"] == tpl_str:
                return dict(tpl)

        clean_id = tpl_str.replace("tpl_", "")
        if clean_id.isdigit():
            stmt = select(FeeTemplateRecord).where(
                FeeTemplateRecord.id == int(clean_id),
            )
        else:
            stmt = select(FeeTemplateRecord).where(
                FeeTemplateRecord.slug == tpl_str,
            )
        if user_id:
            stmt = stmt.where(FeeTemplateRecord.user_id == user_id)
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return None

        return {
            "id": f"tpl_{record.id}",
            "slug": record.slug,
            "template_name": record.name,
            "name": record.name,
            "platform": record.platform,
            "region": record.region,
            "currency": record.withdrawal_currency,
            "contract_service_fee_pct": record.contract_service_fee_pct,
            "contract_service_fee_fixed": record.contract_service_fee_fixed,
            "fee_tax_pct": record.tax_on_fee_pct,
            "tax_on_fee_pct": record.tax_on_fee_pct,
            "withholding_tax_pct": record.withholding_tax_pct,
            "withholding_tax_base": record.withholding_base,
            "withholding_base": record.withholding_base,
            "withdrawal_fee": record.withdrawal_fee,
            "withdrawal_currency": record.withdrawal_currency,
            "processor_fee_pct": record.processor_charge_pct,
            "processor_charge_pct": record.processor_charge_pct,
            "processor_fee_fixed": record.processor_charge_fixed,
            "processor_charge_fixed": record.processor_charge_fixed,
            "source_url": record.source_url,
            "effective_date": record.effective_date,
            "eligibility_notes": record.eligibility_notes,
            "is_system": False,
            "is_system_template": False,
            "is_active": True,
        }

    async def create_custom_template(
        self, user_id: str, data: dict[str, Any]
    ) -> FeeTemplateRecord:
        """Create a user custom fee template."""
        now = datetime.now(timezone.utc)
        name = data.get("template_name") or data.get("name") or "My Custom Template"
        slug = f"user_{user_id[:8]}_{uuid.uuid4().hex[:6]}"

        record = FeeTemplateRecord(
            slug=slug,
            user_id=user_id,
            name=name,
            platform=data.get("platform", "custom"),
            region=data.get("region", "GLOBAL"),
            contract_service_fee_pct=float(data.get("contract_service_fee_pct", 0.0)),
            contract_service_fee_fixed=float(data.get("contract_service_fee_fixed", 0.0)),
            tax_on_fee_pct=float(data.get("fee_tax_pct", data.get("tax_on_fee_pct", 0.0))),
            withholding_tax_pct=float(data.get("withholding_tax_pct", 0.0)),
            withholding_base=data.get("withholding_tax_base", data.get("withholding_base", "gross")),
            withdrawal_fee=float(data.get("withdrawal_fee", 0.0)),
            withdrawal_currency=data.get("currency", "USD").upper(),
            processor_charge_pct=float(data.get("processor_fee_pct", data.get("processor_charge_pct", 0.0))),
            processor_charge_fixed=float(data.get("processor_fee_fixed", data.get("processor_charge_fixed", 0.0))),
            source_url=data.get("source_url", ""),
            effective_date=data.get("effective_date", now.strftime("%Y-%m-%d")),
            eligibility_notes=data.get("eligibility_notes", "User custom fee configuration"),
            is_system_template=False,
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def delete_custom_template(self, template_id: str | int, user_id: str) -> bool:
        """Delete a user custom template."""
        tpl_str = str(template_id).replace("tpl_", "")
        if tpl_str.isdigit():
            stmt = select(FeeTemplateRecord).where(
                FeeTemplateRecord.id == int(tpl_str),
                FeeTemplateRecord.user_id == user_id,
            )
        else:
            stmt = select(FeeTemplateRecord).where(
                FeeTemplateRecord.slug == str(template_id),
                FeeTemplateRecord.user_id == user_id,
            )
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return False

        await self.session.delete(record)
        await self.session.commit()
        return True
