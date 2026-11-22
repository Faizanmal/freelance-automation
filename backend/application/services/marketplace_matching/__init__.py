"""Phase 15 — Fair Two-Sided Marketplace Matching & Mutual-Interest Hiring."""

from backend.application.services.marketplace_matching.conversation_service import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_SIZE_BYTES,
    ProjectConversationService,
)
from backend.application.services.marketplace_matching.evaluation_metrics import (
    EvaluationMetricsCalculator,
    MatchingEvaluationMetrics,
)
from backend.application.services.marketplace_matching.matcher import (
    CandidateMatch,
    FairMarketplaceMatcher,
    MatchBreakdown,
    TalentFeatureVector,
)
from backend.application.services.marketplace_matching.mutual_interest_service import (
    ProjectMutualInterestService,
)
from backend.application.services.marketplace_matching.negotiation_service import (
    ConflictError,
    NegotiationAssistant,
    ProjectNegotiationService,
)

__all__ = [
    "ALLOWED_ATTACHMENT_EXTENSIONS",
    "CandidateMatch",
    "ConflictError",
    "EvaluationMetricsCalculator",
    "FairMarketplaceMatcher",
    "MAX_ATTACHMENT_SIZE_BYTES",
    "MatchBreakdown",
    "MatchingEvaluationMetrics",
    "NegotiationAssistant",
    "ProjectConversationService",
    "ProjectMutualInterestService",
    "ProjectNegotiationService",
    "TalentFeatureVector",
]
