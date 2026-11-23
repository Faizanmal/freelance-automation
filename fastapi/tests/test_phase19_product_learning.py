"""Privacy and event-contract checks for Phase 19 analytics."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.ops import _product_event_cell
from app.api.v1.telemetry import ClientErrorIn, ProductEventBatch, ProductEventIn
from app.product_events import PRODUCT_EVENT_NAMES
from config.settings import Settings


def test_event_dictionary_is_bounded_and_covers_reported_outcomes():
    assert "external_apply_clicked" in PRODUCT_EVENT_NAMES
    assert "application_confirmed" in PRODUCT_EVENT_NAMES
    assert "cash_received_self_reported" in PRODUCT_EVENT_NAMES
    assert "native_project_response_recorded" in PRODUCT_EVENT_NAMES
    assert "native_dispute_filed" in PRODUCT_EVENT_NAMES


def test_event_payload_rejects_free_form_or_private_fields():
    with pytest.raises(ValidationError):
        ProductEventIn(
            event_key=uuid4(), event_name="hunt_completed",
            occurred_at=datetime.now(timezone.utc), prompt="private prompt text",
        )
    with pytest.raises(ValidationError):
        ProductEventIn(
            event_key=uuid4(), event_name="arbitrary_event",
            occurred_at=datetime.now(timezone.utc),
        )


def test_events_are_deduplicated_by_client_generated_key_contract():
    event_id = uuid4()
    batch = ProductEventBatch(events=[
        {"event_key": str(event_id), "event_name": "lead_saved", "occurred_at": datetime.now(timezone.utc)}
    ])
    assert batch.events[0].event_key == event_id


def test_product_learning_cells_show_unknown_and_suppress_small_cohorts():
    assert _product_event_cell(0, 0) == {
        "events": None, "people": None, "status": "no_observations"
    }
    assert _product_event_cell(6, 6)["status"] == "suppressed_small_cohort"
    assert _product_event_cell(16, 12) == {
        "events": 16, "people": 12, "status": "measured"
    }


def test_client_error_telemetry_cannot_accept_raw_exception_content():
    assert ClientErrorIn(kind="runtime_error").kind == "runtime_error"
    with pytest.raises(ValidationError):
        ClientErrorIn(kind="runtime_error", message="private user input")
    with pytest.raises(ValidationError):
        ClientErrorIn(kind="runtime_error", stack="token or private data")


def test_production_billing_is_off_even_when_credentials_exist_without_explicit_gates():
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        JWT_SECRET_KEY="x" * 40,
        CORS_ORIGINS="https://example.test",
        STRIPE_SECRET_KEY="sk_live_placeholder",
        STRIPE_PRICE_PRO="price_placeholder",
        STRIPE_WEBHOOK_SECRET="whsec_placeholder",
        STRIPE_CHECKOUT_ENABLED=True,
    )
    assert settings.stripe_enabled is False

    approved = Settings(
        _env_file=None,
        APP_ENV="production",
        JWT_SECRET_KEY="x" * 40,
        CORS_ORIGINS="https://example.test",
        STRIPE_SECRET_KEY="sk_live_placeholder",
        STRIPE_PRICE_PRO="price_placeholder",
        STRIPE_WEBHOOK_SECRET="whsec_placeholder",
        STRIPE_CHECKOUT_ENABLED=True,
        STRIPE_LIVE_CHARGES_ENABLED=True,
    )
    assert approved.stripe_enabled is True
