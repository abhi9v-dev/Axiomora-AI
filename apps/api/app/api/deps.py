"""Shared FastAPI dependency providers for app.api.runs.

Each is overridable via `app.dependency_overrides` in tests -- the same
pattern app.api.health already uses for get_database_ping -- so route
tests can substitute fakes without a real database, LLM or embedding call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.action.power_bi.base import PowerBIAdapter
from app.action.power_bi.factory import get_power_bi_adapter
from app.config import Settings, get_settings
from app.db.session import get_engine
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import get_embedding_provider
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.orchestrator.service import OrchestratorParams


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with session_factory() as session:
        yield session


def get_settings_dep() -> Settings:
    return get_settings()


def get_llm_provider_dep() -> LLMProvider:
    return get_llm_provider(get_settings())


def get_embedding_provider_dep() -> EmbeddingProvider:
    return get_embedding_provider(get_settings())


def get_power_bi_adapter_dep() -> PowerBIAdapter:
    return get_power_bi_adapter(get_settings())


def get_orchestrator_params() -> OrchestratorParams:
    settings = get_settings()
    return OrchestratorParams(
        max_repairs=settings.MAX_SQL_REPAIRS,
        timeout_ms=settings.QUERY_TIMEOUT_MS,
        row_limit=settings.QUERY_ROW_LIMIT,
        retrieval_min_score=settings.RETRIEVAL_MIN_SCORE,
        nl2sql_min_confidence=settings.NL2SQL_MIN_CONFIDENCE,
    )
