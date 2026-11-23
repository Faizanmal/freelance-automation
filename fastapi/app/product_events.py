"""Minimal event vocabulary; never accept free-form analytics payloads."""

PRODUCT_EVENT_NAMES = {
    "acquisition_landing_viewed", "activation_onboarding_completed", "hunt_completed",
    "first_qualified_lead", "lead_saved", "lead_skipped", "external_apply_clicked", "application_confirmed",
    "application_reply_recorded", "interview_reported", "contract_acknowledged",
    "cash_received_self_reported", "alert_opted_out", "report_submitted",
    "subscription_started", "subscription_canceled", "native_project_shortlisted",
    "native_project_response_recorded", "native_contract_completed", "native_dispute_filed",
}
