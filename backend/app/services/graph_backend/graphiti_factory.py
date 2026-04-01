"""Graphiti factory and dependency inspection for the cutover backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from importlib import import_module
from typing import Any

from .errors import GraphBackendDependencyError
from .settings import GraphBackendSettings
from .types import GraphDependencyStatus


@dataclass(frozen=True)
class GraphitiFactoryScaffold:
    """Graphiti factory metadata with lazy runtime construction."""

    distribution_name: str
    client_builder: str
    dependency_status: GraphDependencyStatus
    client_kwargs: dict[str, Any] = field(default_factory=dict)
    model_config: dict[str, Any] = field(default_factory=dict)
    openai_config: dict[str, Any] = field(default_factory=dict)

    def build_client(self) -> Any:
        """Build one Graphiti client lazily when the runtime dependency exists."""
        runtime = resolve_graphiti_runtime()

        llm_config_kwargs = {
            "api_key": self.openai_config.get("api_key"),
            "model": self.model_config.get("extraction_model"),
            "small_model": self.model_config.get("extraction_model"),
            "base_url": self.openai_config.get("base_url"),
        }
        llm_config = runtime["LLMConfig"](
            **{key: value for key, value in llm_config_kwargs.items() if value not in (None, "")}
        )
        llm_client = runtime["OpenAIGenericClient"](config=llm_config)

        embedder_config_kwargs = {
            "api_key": self.openai_config.get("embedding_api_key")
            or self.openai_config.get("api_key"),
            "embedding_model": self.model_config.get("embedding_model"),
            "base_url": self.openai_config.get("embedding_base_url")
            or self.openai_config.get("base_url"),
            "embedding_dim": self.openai_config.get("embedding_dimensions"),
        }
        embedder_config = runtime["OpenAIEmbedderConfig"](
            **{
                key: value
                for key, value in embedder_config_kwargs.items()
                if value not in (None, "")
            }
        )
        embedder = runtime["OpenAIEmbedder"](config=embedder_config)

        return runtime["Graphiti"](
            self.client_kwargs["uri"],
            self.client_kwargs["user"],
            self.client_kwargs["password"],
            llm_client=llm_client,
            embedder=embedder,
        )

    def get_episode_type(self, member_name: str = "text") -> Any:
        """Resolve one Graphiti `EpisodeType` member lazily."""
        runtime = resolve_graphiti_runtime()
        episode_type = runtime["EpisodeType"]
        return getattr(episode_type, member_name)


def _resolve_symbol(module_paths: tuple[str, ...], symbol_name: str) -> Any:
    last_error: Exception | None = None
    for module_path in module_paths:
        try:
            module = import_module(module_path)
        except Exception as exc:  # pragma: no cover - only exercised with runtime installed
            last_error = exc
            continue
        if hasattr(module, symbol_name):
            return getattr(module, symbol_name)
    detail = f"{symbol_name} was not found in the installed Graphiti runtime"
    if last_error is not None:
        detail = f"{detail}: {last_error}"
    raise GraphBackendDependencyError(detail)


def resolve_graphiti_runtime() -> dict[str, Any]:
    """Resolve Graphiti runtime classes only when needed."""
    dependency_status = detect_graphiti_dependency()
    if not dependency_status.available:
        raise GraphBackendDependencyError(
            dependency_status.detail
            or "graphiti-core is not installed in the backend environment"
        )
    return {
        "Graphiti": _resolve_symbol(("graphiti_core", "graphiti"), "Graphiti"),
        "LLMConfig": _resolve_symbol(("graphiti_core.llm_client.config",), "LLMConfig"),
        "OpenAIGenericClient": _resolve_symbol(
            ("graphiti_core.llm_client.openai_generic_client",),
            "OpenAIGenericClient",
        ),
        "OpenAIEmbedder": _resolve_symbol(
            ("graphiti_core.embedder.openai",),
            "OpenAIEmbedder",
        ),
        "OpenAIEmbedderConfig": _resolve_symbol(
            ("graphiti_core.embedder.openai",),
            "OpenAIEmbedderConfig",
        ),
        "EpisodeType": _resolve_symbol(("graphiti_core.nodes",), "EpisodeType"),
    }


def detect_graphiti_dependency() -> GraphDependencyStatus:
    """Inspect Graphiti availability without importing the runtime package."""
    try:
        version = metadata.version("graphiti-core")
        return GraphDependencyStatus(
            distribution_name="graphiti-core",
            available=True,
            version=version,
        )
    except metadata.PackageNotFoundError:
        return GraphDependencyStatus(
            distribution_name="graphiti-core",
            available=False,
            detail="Install graphiti-core to enable the cutover backend.",
        )


def build_graphiti_factory(_settings: GraphBackendSettings) -> GraphitiFactoryScaffold:
    """Return lazy Graphiti factory metadata for the cutover backend."""
    dependency_status = detect_graphiti_dependency()
    return GraphitiFactoryScaffold(
        distribution_name=dependency_status.distribution_name,
        client_builder="async_graphiti",
        dependency_status=dependency_status,
        client_kwargs={
            "uri": _settings.neo4j_uri,
            "user": _settings.neo4j_user,
            "password": _settings.neo4j_password,
        },
        model_config={
            "extraction_model": _settings.graphiti_extraction_model,
            "embedding_model": _settings.graphiti_embedding_model,
        },
        openai_config={
            "api_key": _settings.openai_api_key,
            "base_url": _settings.openai_base_url,
            "embedding_api_key": _settings.embedding_api_key,
            "embedding_base_url": _settings.embedding_base_url,
            "embedding_dimensions": _settings.embedding_dimensions,
        },
    )
