"""Phase 13 — Employer organization, membership roles, seat lifecycle and access audit logs."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.network import EmployerOrg, OrgMembership, OrgSeatLog
from database.models.user import User

VALID_ORG_ROLES = {"owner", "admin", "hiring_manager", "member"}
VALID_SEAT_STATUSES = {"invited", "active", "suspended", "revoked"}


class OrgService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_organization(
        self,
        owner_id: str,
        name: str,
        website: str | None = None,
        industry: str = "technology",
        org_domain: str | None = None,
        is_sample: bool = False,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> EmployerOrg:
        name_clean = name.strip()
        if not name_clean:
            raise ValueError("Organization name cannot be blank")

        base_slug = re.sub(r"[^a-z0-9]+", "-", name_clean.lower()).strip("-")
        if not base_slug:
            base_slug = f"org-{uuid4().hex[:8]}"
        slug = base_slug

        # Ensure slug uniqueness
        counter = 1
        while True:
            existing = await self.session.execute(
                select(EmployerOrg).where(EmployerOrg.slug == slug)
            )
            if existing.scalar_one_or_none() is None:
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        now = datetime.now(timezone.utc)
        org_id = str(uuid4())
        org = EmployerOrg(
            id=org_id,
            name=name_clean[:256],
            slug=slug[:128],
            website=website.strip()[:256] if website else None,
            industry=industry.strip()[:128] if industry else "technology",
            org_domain=org_domain.strip().lower()[:128] if org_domain else None,
            domain_verified=False,
            verification_status="unverified",
            owner_id=owner_id,
            is_sample=is_sample,
            created_at=now,
            updated_at=now,
        )
        self.session.add(org)
        await self.session.flush()

        # Fetch owner user to retrieve email
        owner_res = await self.session.execute(select(User).where(User.id == owner_id))
        owner = owner_res.scalar_one_or_none()
        owner_email = owner.email if owner else f"owner-{owner_id[:8]}@example.com"

        # Create owner membership
        owner_membership = OrgMembership(
            id=str(uuid4()),
            org_id=org_id,
            user_id=owner_id,
            email=owner_email,
            role="owner",
            seat_status="active",
            invitation_token=None,
            invited_by_id=owner_id,
            invited_at=now,
            accepted_at=now,
            updated_at=now,
        )
        self.session.add(owner_membership)

        # Record audit log
        log = OrgSeatLog(
            id=str(uuid4()),
            org_id=org_id,
            actor_id=owner_id,
            target_user_id=owner_id,
            action="organization_created",
            ip_address=ip_address,
            user_agent=user_agent,
            details={"org_name": name_clean, "role": "owner"},
            created_at=now,
        )
        self.session.add(log)
        await self.session.commit()

        return org

    async def get_org_by_id(self, org_id: str) -> EmployerOrg | None:
        stmt = (
            select(EmployerOrg)
            .where(EmployerOrg.id == org_id)
            .options(
                selectinload(EmployerOrg.members),
                selectinload(EmployerOrg.seat_logs),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_organizations(self, user_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(OrgMembership)
            .where(
                OrgMembership.user_id == user_id,
                OrgMembership.seat_status.in_(["active", "invited"]),
            )
            .options(selectinload(OrgMembership.org))
        )
        res = await self.session.execute(stmt)
        memberships = res.scalars().all()

        results = []
        for m in memberships:
            if m.org:
                results.append({
                    "org_id": m.org.id,
                    "name": m.org.name,
                    "slug": m.org.slug,
                    "role": m.role,
                    "seat_status": m.seat_status,
                    "domain_verified": m.org.domain_verified,
                    "verification_status": m.org.verification_status,
                })
        return results

    async def verify_user_org_permission(
        self, org_id: str, user_id: str, required_roles: set[str] | None = None
    ) -> OrgMembership:
        """Verify user is a member of the organization and has at least one of the required roles."""
        stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
            OrgMembership.seat_status == "active",
        )
        res = await self.session.execute(stmt)
        membership = res.scalar_one_or_none()

        if not membership:
            raise PermissionError("Access denied: You are not an active member of this organization")

        if required_roles and membership.role not in required_roles:
            raise PermissionError(
                f"Insufficient permissions: Required {required_roles}, your role is {membership.role}"
            )
        return membership

    async def verify_user_in_org(self, org_id: str, user_id: str) -> bool:
        """Check if user has an active membership in the organization."""
        stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
            OrgMembership.seat_status == "active",
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def invite_member(
        self,
        org_id: str,
        actor_id: str,
        email: str,
        role: str = "member",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> OrgMembership:
        # Only owner or admin can invite
        await self.verify_user_org_permission(org_id, actor_id, {"owner", "admin"})

        email_clean = email.strip().lower()
        if not email_clean or "@" not in email_clean:
            raise ValueError("Valid email is required")

        role_clean = role.strip().lower()
        if role_clean not in {"admin", "hiring_manager", "member"}:
            raise ValueError("Role must be admin, hiring_manager, or member")

        # Check existing membership
        existing_stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.email == email_clean,
            OrgMembership.seat_status.in_(["active", "invited"]),
        )
        existing = (await self.session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ValueError("User or email already has an active or invited seat in this organization")

        # Check if user already exists in DB
        user_res = await self.session.execute(select(User).where(User.email == email_clean))
        target_user = user_res.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        invitation_token = f"inv_{uuid4().hex}"

        membership = OrgMembership(
            id=str(uuid4()),
            org_id=org_id,
            user_id=target_user.id if target_user else None,
            email=email_clean,
            role=role_clean,
            seat_status="invited",
            invitation_token=invitation_token,
            invited_by_id=actor_id,
            invited_at=now,
            updated_at=now,
        )
        self.session.add(membership)

        # Audit log
        log = OrgSeatLog(
            id=str(uuid4()),
            org_id=org_id,
            actor_id=actor_id,
            target_user_id=target_user.id if target_user else None,
            action="invite_sent",
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email_clean, "role": role_clean},
            created_at=now,
        )
        self.session.add(log)
        await self.session.commit()
        return membership

    async def accept_invitation(
        self,
        invitation_token: str,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> OrgMembership:
        stmt = select(OrgMembership).where(
            OrgMembership.invitation_token == invitation_token,
            OrgMembership.seat_status == "invited",
        )
        res = await self.session.execute(stmt)
        membership = res.scalar_one_or_none()
        if not membership:
            raise ValueError("Invalid or expired invitation token")

        now = datetime.now(timezone.utc)
        membership.user_id = user.id
        membership.email = user.email
        membership.seat_status = "active"
        membership.invitation_token = None
        membership.accepted_at = now
        membership.updated_at = now

        log = OrgSeatLog(
            id=str(uuid4()),
            org_id=membership.org_id,
            actor_id=user.id,
            target_user_id=user.id,
            action="invite_accepted",
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": user.email, "role": membership.role},
            created_at=now,
        )
        self.session.add(log)
        await self.session.commit()
        return membership

    async def update_member_role(
        self,
        org_id: str,
        actor_id: str,
        membership_id: str,
        new_role: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> OrgMembership:
        actor_mem = await self.verify_user_org_permission(org_id, actor_id, {"owner", "admin"})

        new_role_clean = new_role.strip().lower()
        if new_role_clean not in {"admin", "hiring_manager", "member"}:
            raise ValueError("Invalid role assignment")

        stmt = select(OrgMembership).where(
            OrgMembership.id == membership_id,
            OrgMembership.org_id == org_id,
        )
        res = await self.session.execute(stmt)
        target_mem = res.scalar_one_or_none()
        if not target_mem:
            raise ValueError("Membership record not found")

        if target_mem.role == "owner":
            raise ValueError("Cannot alter owner role. Transfer ownership instead.")

        if actor_mem.role == "admin" and target_mem.role == "admin" and actor_mem.id != target_mem.id:
            raise PermissionError("Admins cannot alter other admins; only owners can modify admin roles.")

        now = datetime.now(timezone.utc)
        old_role = target_mem.role
        target_mem.role = new_role_clean
        target_mem.updated_at = now

        log = OrgSeatLog(
            id=str(uuid4()),
            org_id=org_id,
            actor_id=actor_id,
            target_user_id=target_mem.user_id,
            action="role_changed",
            ip_address=ip_address,
            user_agent=user_agent,
            details={"old_role": old_role, "new_role": new_role_clean},
            created_at=now,
        )
        self.session.add(log)
        await self.session.commit()
        return target_mem

    async def revoke_seat(
        self,
        org_id: str,
        actor_id: str,
        membership_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> OrgMembership:
        actor_mem = await self.verify_user_org_permission(org_id, actor_id, {"owner", "admin"})

        stmt = select(OrgMembership).where(
            OrgMembership.id == membership_id,
            OrgMembership.org_id == org_id,
        )
        res = await self.session.execute(stmt)
        target_mem = res.scalar_one_or_none()
        if not target_mem:
            raise ValueError("Membership record not found")

        if target_mem.role == "owner":
            raise ValueError("Cannot revoke organization owner seat")

        if actor_mem.role == "admin" and target_mem.role == "admin" and actor_mem.id != target_mem.id:
            raise PermissionError("Admins cannot revoke other admins")

        now = datetime.now(timezone.utc)
        target_mem.seat_status = "revoked"
        target_mem.revoked_at = now
        target_mem.updated_at = now

        log = OrgSeatLog(
            id=str(uuid4()),
            org_id=org_id,
            actor_id=actor_id,
            target_user_id=target_mem.user_id,
            action="seat_revoked",
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": target_mem.email, "role": target_mem.role},
            created_at=now,
        )
        self.session.add(log)
        await self.session.commit()
        return target_mem

    async def get_org_audit_logs(
        self, org_id: str, actor_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        await self.verify_user_org_permission(org_id, actor_id, {"owner", "admin"})

        stmt = (
            select(OrgSeatLog)
            .where(OrgSeatLog.org_id == org_id)
            .order_by(OrgSeatLog.created_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        logs = res.scalars().all()

        return [
            {
                "id": log.id,
                "action": log.action,
                "actor_id": log.actor_id,
                "target_user_id": log.target_user_id,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
