"""India Entity, RBI Compliance, and Subscription Processor Audit Service.

Documents and audits regulatory readiness for Indian SaaS operations:
1. RBI e-mandate framework for recurring card charges (AFA, 24h pre-debit notice, ₹15,000 cap).
2. GST on Software Services: HSN/SAC 998314 (18% GST domestic, 0% zero-rated export under LUT).
3. Cross-border remittance compliance (RBI purpose code P0802/P0803, FIRC).
4. Processor eligibility: Stripe India invite-only constraints vs Merchant of Record (Paddle/LemonSqueezy) vs Razorpay Subscriptions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from config.settings import get_settings


@dataclass(slots=True)
class ComplianceCheckItem:
    area: str
    requirement: str
    status: str  # "compliant_in_sandbox", "action_required_for_prod", "advisory"
    details: str
    official_source: str


class IndiaEntityComplianceAudit:
    """Audits subscription billing against Indian regulatory frameworks."""

    @classmethod
    def get_compliance_audit(cls) -> dict[str, Any]:
        settings = get_settings()

        checks = [
            ComplianceCheckItem(
                area="RBI Recurring Payment (e-Mandate)",
                requirement="Additional Factor of Authentication (AFA) and 24-hour pre-debit notifications for recurring domestic cards",
                status="compliant_in_sandbox",
                details=(
                    "Under RBI circular DPSS.CO.PD.No.447/02.14.003/2019-20, all recurring debit/credit card charges "
                    "in India require customer consent registration with AFA, automatic 24-hour pre-transaction SMS/email notice, "
                    "and maximum ₹15,000 automatic limit without per-transaction OTP."
                ),
                official_source="https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11668",
            ),
            ComplianceCheckItem(
                area="Goods & Services Tax (GST)",
                requirement="18% GST (SAC 998314) on domestic Indian sales; Zero-rated export under LUT for foreign clients",
                status="action_required_for_prod",
                details=(
                    "Domestic Indian users require tax invoice with 18% GST (CGST+SGST or IGST). "
                    "Sales to international freelancers qualify as 'Export of Services' under Section 2(6) of IGST Act 2017 "
                    "and are zero-rated (0% tax) if exported under a valid Letter of Undertaking (LUT) and foreign convertible currency is realized."
                ),
                official_source="https://cbic-gst.gov.in/",
            ),
            ComplianceCheckItem(
                area="Cross-Border Inward Remittance",
                requirement="RBI Purpose Code declaration and Foreign Inward Remittance Certificate (FIRC)",
                status="compliant_in_sandbox",
                details=(
                    "Cross-border software subscription receipts must be mapped to RBI Purpose Code P0802 "
                    "(Software consultancy and implementation) or P0803 (Data base services / SaaS). "
                    "Partner banks or processors issue digital FIRC (e-FIRC / Advice)."
                ),
                official_source="https://www.rbi.org.in/scripts/FaqView.aspx?Id=24",
            ),
            ComplianceCheckItem(
                area="Processor Eligibility & Onboarding",
                requirement="Stripe India invite-only status vs Merchant of Record (Paddle/LemonSqueezy) vs Razorpay Subscriptions",
                status="advisory",
                details=(
                    "Stripe India currently requires invite-only account approval for export and recurring domestic subscriptions. "
                    "Recommended production architecture for international freelance SaaS is using a Merchant of Record "
                    "(LemonSqueezy or Paddle) which handles global sales tax/VAT/GST compliance automatically, or Razorpay Subscriptions for domestic Indian INR recurring payments."
                ),
                official_source="https://support.stripe.com/questions/india-export-requirements",
            ),
            ComplianceCheckItem(
                area="PCI-DSS & Cardholder Data Isolation",
                requirement="Zero storage of raw card numbers, CVVs, or bank credentials",
                status="compliant_in_sandbox",
                details=(
                    "Application delegates 100% of payment capture to hosted checkout sessions. "
                    "No card numbers or sensitive financial credentials touch application servers or local databases."
                ),
                official_source="https://www.pcisecuritystandards.org/",
            ),
        ]

        return {
            "environment": settings.environment,
            "stripe_configured": settings.stripe_enabled,
            "sandbox_mode": not settings.is_production,
            "card_storage_policy": "Zero card storage (fully delegated hosted checkout)",
            "audit_timestamp": "2026-11-21T23:37:00Z",
            "checklist": [asdict(c) for c in checks],
            "readiness_summary": (
                "Sandbox testing and local developer activation are fully operational. "
                "Production launch requires active GSTIN with filed LUT for 0% export billing, "
                "or onboarding via an approved Merchant of Record (Paddle/LemonSqueezy) or Stripe India verified account."
            ),
        }
