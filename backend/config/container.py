from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.job_enrichment_service import (
    DomainJobEnrichmentService,
)
from backend.application.services.job_match_service import DomainJobMatchService
from backend.domain.interfaces import (
    IConfigProvider,
    IJobEnrichmentService,
    IJobMatchService,
    IJobRepository,
)
from backend.infrastructure.di import DIContainer
from backend.infrastructure.repositories.job_repository import DomainJobRepository


class EnvConfigProvider:
    def get(self, key: str, default: Any = None) -> Any:
        import os

        return os.getenv(key, default)


container = DIContainer()


def setup_container() -> DIContainer:
    """Wire up the core dependencies."""
    container.register_singleton(IConfigProvider, EnvConfigProvider())

    # Repositories (usually transient or dependent on request-scoped session)
    # Here we define a factory that requires an AsyncSession to be injected or provided.
    container.register_factory(
        IJobRepository, lambda c: DomainJobRepository(c.resolve(AsyncSession))
    )

    # Application Services
    container.register_singleton(IJobMatchService, DomainJobMatchService())
    container.register_singleton(IJobEnrichmentService, DomainJobEnrichmentService())

    return container
