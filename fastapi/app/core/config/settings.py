from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field("Freelance Intelligence API", alias="PROJECT_NAME")
    environment: str = Field("development", alias="APP_ENV")
    version: str = Field("0.5.0", alias="VERSION")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/freelance",
        alias="DATABASE_URL",
    )
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    redis_optional: bool = Field(True, alias="REDIS_OPTIONAL")

    jwt_secret_key: str = Field("dev-secret-change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(60 * 24, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    cors_origins: str = Field("http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ORIGINS")
    scrape_on_startup: bool = Field(False, alias="SCRAPE_ON_STARTUP")
    scrape_interval_minutes: int = Field(0, alias="SCRAPE_INTERVAL_MINUTES")
    scrape_limit: int = Field(30, alias="SCRAPE_LIMIT")
    scrape_notify_matches: bool = Field(True, alias="SCRAPE_NOTIFY_MATCHES")
    scrape_sources: str = Field(
        "remoteok,arbeitnow,himalayas,jobicy", alias="SCRAPE_SOURCES"
    )

    # LLM providers (fallback order: groq > nvidia > gemini > openai > anthropic)
    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.3-70b-versatile", alias="GROQ_MODEL")
    nvidia_api_key: str | None = Field(None, alias="NVIDIA_API_KEY")
    nvidia_model: str = Field("meta/llama-3.1-70b-instruct", alias="NVIDIA_MODEL")
    gemini_api_key: str | None = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.0-flash", alias="GEMINI_MODEL")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-5-haiku-latest", alias="ANTHROPIC_MODEL")

    # Upwork official GraphQL API (OAuth 2.0)
    upwork_client_id: str | None = Field(None, alias="UPWORK_CLIENT_ID")
    upwork_client_secret: str | None = Field(None, alias="UPWORK_CLIENT_SECRET")
    upwork_redirect_uri: str = Field(
        "http://127.0.0.1:8000/integrations/upwork/callback",
        alias="UPWORK_REDIRECT_URI",
    )
    upwork_access_token: str | None = Field(None, alias="UPWORK_ACCESS_TOKEN")
    upwork_refresh_token: str | None = Field(None, alias="UPWORK_REFRESH_TOKEN")
    upwork_search_query: str = Field("python OR fastapi OR react", alias="UPWORK_SEARCH_QUERY")

    # Freelancer.com official API
    freelancer_oauth_token: str | None = Field(None, alias="FREELANCER_OAUTH_TOKEN")
    freelancer_search_query: str = Field("python", alias="FREELANCER_SEARCH_QUERY")

    # Optional community connectors for platforms without public job-search APIs.
    apify_token: str | None = Field(None, alias="APIFY_TOKEN")
    peopleperhour_actor_id: str = Field(
        "crawlerbros/peopleperhour-scraper",
        alias="PEOPLEPERHOUR_ACTOR_ID",
    )
    peopleperhour_search_query: str = Field(
        "python",
        alias="PEOPLEPERHOUR_SEARCH_QUERY",
    )
    guru_actor_id: str = Field(
        "shahidirfan/guru-com-scraper",
        alias="GURU_ACTOR_ID",
    )
    guru_search_query: str = Field("python", alias="GURU_SEARCH_QUERY")

    # SerpAPI discovery (Google organic + Jobs + Maps + company careers) — Pro, billed by SerpAPI
    serpapi_api_key: str | None = Field(None, alias="SERPAPI_API_KEY")
    serpapi_freelance_query: str = Field(
        '("looking for" OR hiring OR need) (freelancer OR contractor) (python OR fastapi OR react) -course -tutorial',
        alias="SERPAPI_FREELANCE_QUERY",
    )
    serpapi_jobs_query: str = Field(
        "python OR fastapi OR react remote developer",
        alias="SERPAPI_JOBS_QUERY",
    )
    # Keyword prefix only; site: batches come from serpapi_company_sites / built-in allowlist.
    serpapi_companies_query: str = Field(
        '(careers OR "we\'re hiring" OR "open roles" OR jobs) (python OR fastapi OR react)',
        alias="SERPAPI_COMPANIES_QUERY",
    )
    serpapi_company_sites: str = Field(
        "",
        alias="SERPAPI_COMPANY_SITES",
        description=(
            "Comma-separated company career hosts. Empty uses the built-in allowlist "
            "(company sites + low-traffic ATS tenants; high-traffic boards excluded)."
        ),
    )
    serpapi_maps_query: str = Field(
        "software agencies OR startups hiring developers",
        alias="SERPAPI_MAPS_QUERY",
    )
    serpapi_maps_ll: str = Field("", alias="SERPAPI_MAPS_LL")
    serpapi_location: str = Field("", alias="SERPAPI_LOCATION")
    serpapi_gl: str = Field("us", alias="SERPAPI_GL")
    serpapi_hl: str = Field("en", alias="SERPAPI_HL")

    # Stripe billing (optional until keys are set)
    stripe_secret_key: str | None = Field(None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_pro: str | None = Field(None, alias="STRIPE_PRICE_PRO")
    stripe_success_url: str = Field(
        "http://localhost:3000/preferences?billing=success",
        alias="STRIPE_SUCCESS_URL",
    )
    stripe_cancel_url: str = Field(
        "http://localhost:3000/pricing?billing=cancel",
        alias="STRIPE_CANCEL_URL",
    )
    public_app_url: str = Field("http://localhost:3000", alias="PUBLIC_APP_URL")

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.lower() != "production":
            return self

        if self.jwt_secret_key == "dev-secret-change-me" or len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be a random value of at least 32 characters in production")
        if not self.cors_origin_list or "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must list explicit frontend origins in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def scrape_source_list(self) -> list[str]:
        return [part.strip() for part in self.scrape_sources.split(",") if part.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_pro)


@lru_cache
def get_settings() -> Settings:
    return Settings()
