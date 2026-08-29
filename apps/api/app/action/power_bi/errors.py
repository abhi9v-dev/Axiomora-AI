"""Power BI adapter error type -- wraps adapter-specific failures (auth,
network, throttling, unexpected API responses, ...) behind one stable
exception, the same role app.llm.errors.LLMProviderError plays for
LLMProvider (ADR 0002: provider interfaces for external dependencies).
Callers never need to know which adapter is in use, and no raw HTTP
response bodies, tokens or connection details leak into logs or
client-facing errors.
"""

from __future__ import annotations


class PowerBIAdapterError(Exception):
    pass
