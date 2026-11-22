"""Phase 15 — Authenticated negotiation messaging, attachment validation, and privacy protection."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.network.org_service import OrgService
from database.models.matching import (
    ProjectApplication,
    ProjectConversation,
    ProjectMessage,
)
from database.models.project import NativeProject

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".zip",
    ".txt",
    ".md",
    ".json",
    ".csv",
}

MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class ProjectConversationService:
    """Handles direct authenticated negotiation conversations between client org and freelancer."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_service = OrgService(session)

    async def get_or_create_conversation(
        self,
        project_id: str,
        freelancer_id: str,
        actor_id: str,
        application_id: str | None = None,
    ) -> ProjectConversation:
        """Find or start a negotiation conversation between client org and freelancer."""
        project_res = await self.session.execute(
            select(NativeProject).where(NativeProject.id == project_id)
        )
        project = project_res.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        # Authorization: actor must be the freelancer or a member of project's org
        is_client = await self.org_service.verify_user_in_org(project.org_id, actor_id)
        if actor_id != freelancer_id and not is_client:
            raise PermissionError("Access denied to project conversation")

        # Check existing conversation
        stmt = select(ProjectConversation).where(
            ProjectConversation.project_id == project_id,
            ProjectConversation.freelancer_id == freelancer_id,
        )
        conv_res = await self.session.execute(stmt)
        conv = conv_res.scalar_one_or_none()

        if not conv:
            now = datetime.now(timezone.utc)
            conv = ProjectConversation(
                id=str(uuid4()),
                project_id=project_id,
                org_id=project.org_id,
                freelancer_id=freelancer_id,
                application_id=application_id,
                status="active",
                last_message_at=now,
                created_at=now,
            )
            self.session.add(conv)
            await self.session.commit()
            await self.session.refresh(conv)

        return conv

    async def send_message(
        self,
        conversation_id: str,
        sender_id: str,
        body: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> ProjectMessage:
        """Send authenticated message with attachment checks and pre-offer contact masking."""
        conv_res = await self.session.execute(
            select(ProjectConversation).where(ProjectConversation.id == conversation_id)
        )
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise ValueError("Conversation not found")

        if conv.status == "blocked":
            raise ValueError("Conversation has been blocked due to safety or participant report")

        # Verify sender role
        is_client = await self.org_service.verify_user_in_org(conv.org_id, sender_id)
        if sender_id == conv.freelancer_id:
            sender_role = "freelancer"
        elif is_client:
            sender_role = "client"
        else:
            raise PermissionError("Access denied: sender is not a participant in this conversation")

        # Sanitize body
        clean_body = body.strip()
        if not clean_body:
            raise ValueError("Message body cannot be empty")

        # Mask off-platform contact details during initial negotiation to protect against external bypass scams
        sanitized_body = self._mask_contact_info_if_needed(clean_body)

        # Validate attachments
        clean_attachments: list[dict[str, Any]] = []
        if attachments:
            for att in attachments:
                clean_att = self._validate_attachment(att)
                clean_attachments.append(clean_att)

        now = datetime.now(timezone.utc)
        msg = ProjectMessage(
            id=str(uuid4()),
            conversation_id=conversation_id,
            sender_id=sender_id,
            sender_role=sender_role,
            body=sanitized_body,
            attachments=clean_attachments,
            is_read=False,
            created_at=now,
        )
        conv.last_message_at = now
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def get_messages(
        self,
        conversation_id: str,
        actor_id: str,
    ) -> list[dict[str, Any]]:
        conv_res = await self.session.execute(
            select(ProjectConversation).where(ProjectConversation.id == conversation_id)
        )
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise ValueError("Conversation not found")

        is_client = await self.org_service.verify_user_in_org(conv.org_id, actor_id)
        if actor_id != conv.freelancer_id and not is_client:
            raise PermissionError("Access denied to conversation messages")

        msg_res = await self.session.execute(
            select(ProjectMessage)
            .where(ProjectMessage.conversation_id == conversation_id)
            .order_by(ProjectMessage.created_at.asc())
        )
        msgs = msg_res.scalars().all()
        return [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_id": m.sender_id,
                "sender_role": m.sender_role,
                "body": m.body,
                "attachments": m.attachments,
                "is_read": m.is_read,
                "read_at": m.read_at.isoformat() if m.read_at else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ]

    async def mark_as_read(
        self,
        conversation_id: str,
        actor_id: str,
    ) -> int:
        """Mark incoming messages as read."""
        msg_res = await self.session.execute(
            select(ProjectMessage).where(
                ProjectMessage.conversation_id == conversation_id,
                ProjectMessage.sender_id != actor_id,
                ProjectMessage.is_read == False,
            )
        )
        unread = msg_res.scalars().all()
        now = datetime.now(timezone.utc)
        for m in unread:
            m.is_read = True
            m.read_at = now
        if unread:
            await self.session.commit()
        return len(unread)

    async def report_or_block_conversation(
        self,
        conversation_id: str,
        reporter_id: str,
        action: str = "report",  # "report", "block"
        reason: str = "Spam or policy violation",
    ) -> ProjectConversation:
        conv_res = await self.session.execute(
            select(ProjectConversation).where(ProjectConversation.id == conversation_id)
        )
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise ValueError("Conversation not found")

        is_client = await self.org_service.verify_user_in_org(conv.org_id, reporter_id)
        if reporter_id != conv.freelancer_id and not is_client:
            raise PermissionError("Access denied to manage this conversation")

        if action == "block":
            conv.status = "blocked"

        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    # -----------------------------------------------------------------------
    # Privacy & Safety Helpers
    # -----------------------------------------------------------------------

    @classmethod
    def _mask_contact_info_if_needed(cls, text: str) -> str:
        """Warn/mask raw emails and phone numbers in early negotiation to keep discussions on-platform."""
        # Email pattern
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        masked = re.sub(email_pattern, "[contact details hidden until offer acceptance]", text)

        # Phone pattern (7+ consecutive digits)
        phone_pattern = r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        masked = re.sub(phone_pattern, "[phone number hidden until offer acceptance]", masked)
        return masked

    @classmethod
    def _validate_attachment(cls, att: dict[str, Any]) -> dict[str, Any]:
        filename = str(att.get("filename", "")).strip()
        url = str(att.get("url", "")).strip()
        size_bytes = int(att.get("size_bytes", 0))

        if not filename or not url:
            raise ValueError("Attachment must have a filename and url")

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise ValueError(
                f"Attachment file extension '{ext}' is not permitted. "
                f"Allowed formats: {', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}"
            )

        if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError(
                f"Attachment size exceeds max limit of {MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)}MB"
            )

        # Generate sha256 reference
        sha256 = att.get("sha256") or hashlib.sha256(url.encode()).hexdigest()

        return {
            "filename": filename,
            "url": url,
            "size_bytes": size_bytes,
            "mime": att.get("mime", "application/octet-stream"),
            "sha256": sha256,
        }
