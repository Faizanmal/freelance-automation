from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import freelancer as freelancer_api
from app.integrations import upwork as upwork_api
from database.models.application import JobApplication
from database.models.job import JobRecord
from database.models.user import User
from backend.application.services.proposal_draft import extract_apply_email, submit_mode_for_source


class ApplyError(RuntimeError):
    def __init__(self, message: str, *, code: str = "apply_failed") -> None:
        super().__init__(message)
        self.code = code


class ApplyService:
    """Submit a reviewed application via the source-specific adapter."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit(
        self,
        *,
        user: User,
        job: JobRecord,
        form_fields: dict[str, Any],
        confirm: bool,
    ) -> dict[str, Any]:
        if not confirm:
            raise ApplyError("Set confirm=true after reviewing the form.", code="confirm_required")

        proposal = str(form_fields.get("proposal") or "").strip()
        if not proposal:
            raise ApplyError("Proposal text is required.", code="proposal_required")

        submit_mode = submit_mode_for_source(job.source_name)
        bid_amount = _to_float(form_fields.get("bid_amount"))
        delivery_days = _to_int(form_fields.get("delivery_days")) or 7
        milestone_percentage = _to_int(form_fields.get("milestone_percentage")) or 100
        currency = str(form_fields.get("currency") or "USD")
        milestone_plan = str(form_fields.get("milestone_plan") or "") or None

        application = JobApplication(
            user_id=user.id,
            job_id=job.id,
            source_name=job.source_name,
            submit_mode=submit_mode,
            status="pending",
            proposal=proposal,
            bid_amount=bid_amount,
            currency=currency,
            delivery_days=delivery_days,
            milestone_plan=milestone_plan,
        )
        self.session.add(application)
        await self.session.flush()

        try:
            if submit_mode == "api_bid" and job.source_name == "freelancer":
                result = await self._submit_freelancer(
                    job=job,
                    proposal=proposal,
                    bid_amount=bid_amount,
                    delivery_days=delivery_days,
                    milestone_percentage=milestone_percentage,
                )
            elif submit_mode == "api_proposal" and job.source_name == "upwork":
                result = await self._submit_upwork(job=job, proposal=proposal)
            elif submit_mode == "email_apply":
                result = await self._submit_email(job=job, user=user, proposal=proposal)
            else:
                raise ApplyError(
                    f"Direct submit is not supported for source '{job.source_name}'.",
                    code="submit_unsupported",
                )
        except ApplyError as exc:
            application.status = "failed"
            application.error = str(exc)
            await self.session.flush()
            raise
        except Exception as exc:  # noqa: BLE001
            application.status = "failed"
            application.error = str(exc)
            await self.session.flush()
            raise ApplyError(str(exc), code="apply_failed") from exc

        application.status = "submitted"
        application.external_id = result.get("external_id")
        application.response_payload = result
        application.error = None
        await self.session.flush()

        return {
            "application_id": application.id,
            "job_id": job.id,
            "source_name": job.source_name,
            "submit_mode": submit_mode,
            "status": application.status,
            "external_id": application.external_id,
            "detail": result.get("detail"),
            "result": result,
        }

    async def _submit_freelancer(
        self,
        *,
        job: JobRecord,
        proposal: str,
        bid_amount: float | None,
        delivery_days: int,
        milestone_percentage: int,
    ) -> dict[str, Any]:
        if bid_amount is None or bid_amount <= 0:
            raise ApplyError("bid_amount is required for Freelancer bids.", code="bid_amount_required")
        try:
            project_id = int(job.source_id)
        except (TypeError, ValueError) as exc:
            raise ApplyError("Invalid Freelancer project id.", code="invalid_project_id") from exc

        bid = await freelancer_api.place_bid(
            project_id=project_id,
            amount=bid_amount,
            period=delivery_days,
            description=proposal,
            milestone_percentage=milestone_percentage,
        )
        return {
            "channel": "freelancer_api",
            "external_id": str(bid.get("id") or bid.get("bid_id") or ""),
            "detail": "Bid placed on Freelancer.com",
            "payload": bid,
        }

    async def _submit_upwork(self, *, job: JobRecord, proposal: str) -> dict[str, Any]:
        if not upwork_api.upwork_configured():
            raise ApplyError(
                "Upwork is not connected. Connect OAuth under Sources first.",
                code="upwork_not_configured",
            )
        # Official proposal mutations vary by account permissions; keep an explicit gate.
        raise ApplyError(
            "Upwork proposal API submit is not enabled for this account integration yet. "
            "Form fill works; connect a proposal-capable Upwork app to finish wiring.",
            code="upwork_submit_unavailable",
        )

    async def _submit_email(self, *, job: JobRecord, user: User, proposal: str) -> dict[str, Any]:
        to_address = extract_apply_email(job)
        if not to_address:
            raise ApplyError(
                "No apply email found on this listing. This public board has no bid API.",
                code="email_not_found",
            )

        smtp_host = os.getenv("EMAIL_SMTP_HOST")
        smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        username = os.getenv("EMAIL_USERNAME")
        password = os.getenv("EMAIL_PASSWORD")
        from_address = os.getenv("EMAIL_FROM")
        if not (smtp_host and username and password and from_address):
            raise ApplyError(
                "EMAIL_SMTP_* settings are required to email applications for public boards.",
                code="email_not_configured",
            )

        message = EmailMessage()
        message["Subject"] = f"Application: {job.title}"
        message["From"] = from_address
        message["To"] = to_address
        message["Reply-To"] = user.email
        message.set_content(
            f"{proposal}\n\n---\nSubmitted via Signal Desk\nListing: {job.url}\nApplicant: {user.email}\n"
        )

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(username, password)
                smtp.send_message(message)
        except Exception as exc:  # noqa: BLE001
            raise ApplyError(f"SMTP send failed: {exc}", code="email_send_failed") from exc

        return {
            "channel": "email",
            "external_id": to_address,
            "detail": f"Application emailed to {to_address}",
        }


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
