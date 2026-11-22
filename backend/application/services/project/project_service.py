"""Phase 14 — Native client project service, lifecycle transitions, hiring intent evidence, and abandonment prevention."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.application.services.network.org_service import OrgService
from backend.application.services.project.scope_clarification import (
    ProjectSafetyScanner,
    ScopeClarificationEngine,
)
from database.models.network import EmployerOrg, OrgMembership
from database.models.project import (
    PROJECT_LEGAL_TRANSITIONS,
    NativeProject,
    ProjectCandidateShortlist,
    ProjectModerationQueue,
    ProjectStatusHistory,
)
from database.models.user import User


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.org_service = OrgService(session)

    async def verify_client_access(
        self, org_id: str, actor_id: str, allowed_roles: set[str] | None = None
    ) -> OrgMembership:
        """Verify actor is a member of the organization with proper hiring privileges."""
        roles = allowed_roles or {"owner", "admin", "hiring_manager"}
        return await self.org_service.verify_user_org_permission(
            org_id=org_id, user_id=actor_id, required_roles=roles
        )

    async def create_project_brief(
        self,
        org_id: str,
        creator_id: str,
        title: str,
        raw_description: str,
        budget_min: float,
        budget_max: float,
        hiring_deadline: datetime,
        currency: str = "USD",
        rate_period: str = "fixed",
        scope_level: str = "medium",
        work_type: str = "remote",
        commitment_type: str = "contract",
        required_hours_per_week: int = 20,
        skills_required: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        milestone_outline: list[dict[str, Any]] | None = None,
        template_key: str | None = None,
        is_sample: bool = False,
    ) -> NativeProject:
        """Create a native project brief in draft status with AI scope clarification and duplicate checks."""
        await self.verify_client_access(org_id, creator_id)

        title_clean = title.strip()
        desc_clean = raw_description.strip()
        if not title_clean:
            raise ValueError("Project title is required")
        if not desc_clean:
            raise ValueError("Project description is required")
        if budget_min <= 0 or budget_max <= 0:
            raise ValueError("Budget must be greater than zero")
        if budget_max < budget_min:
            raise ValueError("Maximum budget cannot be less than minimum budget")

        # Duplicate check: check if same title/description posted by this org recently
        dup_hash = ScopeClarificationEngine.compute_content_hash(
            title_clean, desc_clean, org_id
        )
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt_dup = select(NativeProject).where(
            NativeProject.org_id == org_id,
            NativeProject.duplicate_hash == dup_hash,
            NativeProject.created_at >= since,
            NativeProject.status != "canceled",
        )
        existing_dup = (await self.session.execute(stmt_dup)).scalar_one_or_none()
        if existing_dup:
            raise ValueError(
                "Duplicate project posting detected: An identical project brief was already created by your organization within 24 hours."
            )

        # AI scope clarification
        clarification = ScopeClarificationEngine.clarify_scope(
            raw_description=desc_clean,
            template_key=template_key,
            skills_hint=skills_required,
        )

        final_skills = skills_required or clarification["suggested_skills"]
        final_criteria = acceptance_criteria or clarification["acceptance_criteria"]
        final_milestones = milestone_outline or clarification["milestone_outline"]
        budget_basis = clarification["budget_basis_notes"]

        now = datetime.now(timezone.utc)
        dl = hiring_deadline if hiring_deadline.tzinfo else hiring_deadline.replace(tzinfo=timezone.utc)
        reconfirm = now + timedelta(days=14)

        project_id = str(uuid4())
        project = NativeProject(
            id=project_id,
            org_id=org_id,
            creator_id=creator_id,
            title=title_clean[:256],
            raw_description=desc_clean,
            ai_scope_summary=clarification["clarified_summary"],
            ai_clarification_approved=False,  # Client must approve AI draft
            primary_segment="ai_software_automation",
            scope_level=scope_level,
            work_type=work_type,
            commitment_type=commitment_type,
            required_hours_per_week=max(1, min(168, required_hours_per_week)),
            skills_required=final_skills,
            acceptance_criteria=final_criteria,
            milestone_outline=final_milestones,
            budget_min=budget_min,
            budget_max=budget_max,
            currency=currency.strip().upper()[:8],
            rate_period=rate_period,
            budget_basis_notes=budget_basis,
            hiring_deadline=dl,
            reconfirm_by=reconfirm,
            last_reconfirmed_at=now,
            payment_verified=False,
            status="draft",
            review_state="draft",
            duplicate_hash=dup_hash,
            is_sample=is_sample,
            created_at=now,
            updated_at=now,
        )
        self.session.add(project)
        await self.session.flush()

        # Audit log creation
        history = ProjectStatusHistory(
            id=str(uuid4()),
            project_id=project_id,
            from_status=None,
            to_status="draft",
            action="create_draft",
            actor_id=creator_id,
            reason="Initial project brief draft created",
            created_at=now,
        )
        self.session.add(history)
        await self.session.commit()

        return await self.get_project_by_id(project_id)  # type: ignore

    async def get_project_by_id(self, project_id: str) -> NativeProject | None:
        stmt = (
            select(NativeProject)
            .where(NativeProject.id == project_id)
            .options(
                selectinload(NativeProject.org),
                selectinload(NativeProject.creator),
                selectinload(NativeProject.status_history),
                selectinload(NativeProject.clarification_requests),
                selectinload(NativeProject.shortlisted_candidates),
                selectinload(NativeProject.moderation_queue_entries),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def approve_ai_scope_clarification(
        self, project_id: str, actor_id: str, custom_summary: str | None = None
    ) -> NativeProject:
        project = await self.get_project_by_id(project_id)
        if not project:
            raise ValueError("Project not found")
        await self.verify_client_access(project.org_id, actor_id)

        now = datetime.now(timezone.utc)
        project.ai_clarification_approved = True
        if custom_summary:
            project.ai_scope_summary = custom_summary.strip()
        project.updated_at = now

        history = ProjectStatusHistory(
            id=str(uuid4()),
            project_id=project.id,
            from_status=project.status,
            to_status=project.status,
            action="approve_ai_scope",
            actor_id=actor_id,
            reason="Client approved AI scope clarification breakdown",
            created_at=now,
        )
        self.session.add(history)
        await self.session.commit()
        return project

    async def submit_project(self, project_id: str, actor_id: str) -> NativeProject:
        """Submit project brief for publishing. Enforces safety scan and transitions to approved_open or flagged queue."""
        project = await self.get_project_by_id(project_id)
        if not project:
            raise ValueError("Project not found")
        await self.verify_client_access(project.org_id, actor_id)

        if project.status not in {"draft", "needs_clarification"}:
            raise ValueError(f"Cannot submit project in status '{project.status}'")

        # Run Safety & Content Policy Scanner
        scan = ProjectSafetyScanner.scan_project_content(
            title=project.title,
            description=project.raw_description,
            budget_min=project.budget_min,
            budget_max=project.budget_max,
            acceptance_criteria=project.acceptance_criteria,
        )

        now = datetime.now(timezone.utc)
        prev_status = project.status

        if not scan["passed"]:
            # High-risk project flagged for human review
            project.status = "needs_clarification"
            project.review_state = "flagged_for_human_review"
            project.flagged_reason = scan["reason_code"]
            project.updated_at = now

            queue_entry = ProjectModerationQueue(
                id=str(uuid4()),
                project_id=project.id,
                flagged_by="ai_safety_scanner",
                reason_code=scan["reason_code"] or "policy_violation",
                evidence_summary=scan["evidence_summary"] or "Automated safety violation detected",
                status="pending_review",
                created_at=now,
            )
            self.session.add(queue_entry)

            history = ProjectStatusHistory(
                id=str(uuid4()),
                project_id=project.id,
                from_status=prev_status,
                to_status="needs_clarification",
                action="flag_for_review",
                actor_id=actor_id,
                reason=f"Flagged by safety scanner: {scan['reason_code']}",
                metadata_json=scan,
                created_at=now,
            )
            self.session.add(history)
            await self.session.commit()
            return project

        # Passed automated safety scan -> Transition to approved_open
        project.status = "approved_open"
        project.review_state = "approved"
        project.flagged_reason = None
        project.updated_at = now

        history = ProjectStatusHistory(
            id=str(uuid4()),
            project_id=project.id,
            from_status=prev_status,
            to_status="approved_open",
            action="publish_project",
            actor_id=actor_id,
            reason="Safety scan passed; published to client workspace",
            created_at=now,
        )
        self.session.add(history)
        await self.session.commit()
        return project

    async def transition_project_status(
        self,
        project_id: str,
        actor_id: str,
        target_status: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NativeProject:
        """Execute explicit legal transition with state-machine validation and audit history."""
        project = await self.get_project_by_id(project_id)
        if not project:
            raise ValueError("Project not found")
        await self.verify_client_access(project.org_id, actor_id)

        curr = project.status
        allowed = PROJECT_LEGAL_TRANSITIONS.get(curr, set())
        if target_status not in allowed:
            raise ValueError(
                f"Illegal state transition from '{curr}' to '{target_status}'. Allowed transitions: {sorted(allowed)}"
            )

        now = datetime.now(timezone.utc)
        project.status = target_status
        project.updated_at = now

        # If reopening from expired/closed, extend reconfirm date
        if target_status == "approved_open" and curr in {"closed", "canceled", "expired"}:
            project.reconfirm_by = now + timedelta(days=14)
            project.abandonment_reason = None

        history = ProjectStatusHistory(
            id=str(uuid4()),
            project_id=project.id,
            from_status=curr,
            to_status=target_status,
            action=f"transition_to_{target_status}",
            actor_id=actor_id,
            reason=reason or f"Status transitioned to {target_status}",
            metadata_json=metadata,
            created_at=now,
        )
        self.session.add(history)
        await self.session.commit()
        return project

    async def reconfirm_project(self, project_id: str, actor_id: str) -> NativeProject:
        """Periodic reconfirmation of project brief to avoid auto-expiration and abandonment."""
        project = await self.get_project_by_id(project_id)
        if not project:
            raise ValueError("Project not found")
        await self.verify_client_access(project.org_id, actor_id)

        now = datetime.now(timezone.utc)
        project.last_reconfirmed_at = now
        project.reconfirm_by = now + timedelta(days=14)
        project.updated_at = now

        history = ProjectStatusHistory(
            id=str(uuid4()),
            project_id=project.id,
            from_status=project.status,
            to_status=project.status,
            action="reconfirm_hiring_intent",
            actor_id=actor_id,
            reason="Client reconfirmed active hiring intent for this project",
            created_at=now,
        )
        self.session.add(history)
        await self.session.commit()
        return project

    async def expire_stale_projects(self) -> int:
        """System job: Auto-expire inactive or unconfirmed projects with transparent abandonment reasons."""
        now = datetime.now(timezone.utc)
        stmt = select(NativeProject).where(
            NativeProject.status.in_(["approved_open", "shortlist"]),
            (NativeProject.reconfirm_by < now) | (NativeProject.hiring_deadline < now),
        )
        res = await self.session.execute(stmt)
        stale_projects = res.scalars().all()

        count = 0
        for p in stale_projects:
            deadline = p.hiring_deadline if p.hiring_deadline.tzinfo else p.hiring_deadline.replace(tzinfo=timezone.utc)
            reason = "deadline_passed" if deadline < now else "reconfirmation_expired"
            p.status = "expired"
            p.abandonment_reason = reason
            p.updated_at = now

            history = ProjectStatusHistory(
                id=str(uuid4()),
                project_id=p.id,
                from_status=p.status,
                to_status="expired",
                action="auto_expire_stale",
                actor_id=None,
                reason=f"Auto-expired by hiring-intent watchdog: {reason}",
                created_at=now,
            )
            self.session.add(history)
            count += 1

        if count > 0:
            await self.session.commit()
        return count

    async def shortlist_candidate(
        self, project_id: str, actor_id: str, candidate_id: str, notes: str | None = None
    ) -> ProjectCandidateShortlist:
        project = await self.get_project_by_id(project_id)
        if not project:
            raise ValueError("Project not found")
        await self.verify_client_access(project.org_id, actor_id)

        now = datetime.now(timezone.utc)

        # Check existing shortlist
        stmt = select(ProjectCandidateShortlist).where(
            ProjectCandidateShortlist.project_id == project_id,
            ProjectCandidateShortlist.candidate_id == candidate_id,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.stage = "shortlisted"
            existing.notes = notes
            existing.updated_at = now
            await self.session.commit()
            return existing

        item = ProjectCandidateShortlist(
            id=str(uuid4()),
            project_id=project_id,
            candidate_id=candidate_id,
            stage="shortlisted",
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        self.session.add(item)

        # If project was open, advance to shortlist stage
        if project.status == "approved_open":
            project.status = "shortlist"
            project.updated_at = now

        await self.session.commit()
        return item

    async def update_candidate_stage(
        self,
        project_id: str,
        actor_id: str,
        candidate_id: str,
        new_stage: str,
        notes: str | None = None,
    ) -> ProjectCandidateShortlist:
        project = await self.get_project_by_id(project_id)
        if not project:
            raise ValueError("Project not found")
        await self.verify_client_access(project.org_id, actor_id)

        stmt = select(ProjectCandidateShortlist).where(
            ProjectCandidateShortlist.project_id == project_id,
            ProjectCandidateShortlist.candidate_id == candidate_id,
        )
        item = (await self.session.execute(stmt)).scalar_one_or_none()
        if not item:
            raise ValueError("Candidate not in shortlist")

        now = datetime.now(timezone.utc)
        item.stage = new_stage
        if notes:
            item.notes = notes
        item.updated_at = now

        # Mirror project lifecycle
        if new_stage == "interviewing" and project.status in {"shortlist", "approved_open"}:
            project.status = "interviewing"
            project.updated_at = now
        elif new_stage == "hired" and project.status in {"interviewing", "shortlist", "approved_open"}:
            project.status = "offered_hired"
            project.updated_at = now

        await self.session.commit()
        return item

    def compute_hiring_intent_evidence(
        self, project: NativeProject, org: EmployerOrg
    ) -> dict[str, Any]:
        """Compute observable proof of hiring intent with zero invented fake metrics."""
        now = datetime.now(timezone.utc)
        deadline_days = max(
            0,
            (
                (project.hiring_deadline if project.hiring_deadline.tzinfo else project.hiring_deadline.replace(tzinfo=timezone.utc))
                - now
            ).days,
        )

        # Objective checklist
        checklist = {
            "org_domain_verified": bool(org.domain_verified),
            "org_verification_status": org.verification_status,
            "clear_budget_range": (project.budget_min > 0 and project.budget_max >= project.budget_min),
            "budget_display": f"${project.budget_min:,.0f} - ${project.budget_max:,.0f} {project.currency} ({project.rate_period})",
            "decision_deadline_days_remaining": deadline_days,
            "payment_method_verified": bool(project.payment_verified),
            "payment_status_label": (
                "Verified Deposit Method Attached"
                if project.payment_verified
                else "Unverified Payment Method (Unfunded)"
            ),
            "has_milestones": bool(project.milestone_outline and len(project.milestone_outline) > 0),
            "reconfirmation_active": (
                (project.reconfirm_by if project.reconfirm_by.tzinfo else project.reconfirm_by.replace(tzinfo=timezone.utc))
                > now
            ),
        }

        # Calculate high / medium / unverified intent tier
        points = 0
        if checklist["org_domain_verified"]:
            points += 2
        if checklist["clear_budget_range"]:
            points += 2
        if checklist["has_milestones"]:
            points += 1
        if checklist["payment_method_verified"]:
            points += 2
        if checklist["decision_deadline_days_remaining"] > 0:
            points += 1

        tier = "high" if points >= 6 else "moderate" if points >= 4 else "unverified"

        return {
            "tier": tier,
            "points": points,
            "max_points": 8,
            "checklist": checklist,
            "native_application_fee_usd": 0.0,  # Native applications strictly free!
        }
