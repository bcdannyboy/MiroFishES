"""Task-scoped model routing helpers."""

from dataclasses import replace

from ..config import Config, TaskModelRoute


class TaskModelRouter:
    """Resolve forecast-readiness model routes with compatibility fallbacks."""

    def __init__(self, config_cls=Config):
        self.config_cls = config_cls

    def resolve(
        self,
        task: str,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> TaskModelRoute:
        """Resolve one task route and allow safe per-call overrides."""
        routes = self.config_cls.get_task_model_routes()
        if task not in routes:
            available = ", ".join(sorted(routes))
            raise ValueError(f"Unknown model task '{task}'. Available tasks: {available}")

        route = routes[task]
        return replace(
            route,
            model=model or route.model,
            api_key=api_key or route.api_key,
            base_url=base_url or route.base_url,
        )
