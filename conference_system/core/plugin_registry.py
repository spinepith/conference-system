from __future__ import annotations

from conference_system.core.base_stage import BaseWorkflowStage


class PluginRegistry:
    """Registry for workflow stages."""

    def __init__(self) -> None:
        self._stages: dict[str, BaseWorkflowStage] = {}

    def register(self, stage: BaseWorkflowStage) -> None:
        if not stage.stage_id:
            raise ValueError("Stage must have non-empty stage_id")
        if stage.stage_id in self._stages:
            raise ValueError(f"Stage {stage.stage_id!r} already registered")
        self._stages[stage.stage_id] = stage

    def unregister(self, stage_id: str) -> None:
        self._stages.pop(stage_id, None)

    def get(self, stage_id: str) -> BaseWorkflowStage:
        try:
            return self._stages[stage_id]
        except KeyError as exc:
            raise KeyError(f"Stage {stage_id!r} is not registered") from exc

    def list(self) -> list[BaseWorkflowStage]:
        return list(self._stages.values())

    def clear(self) -> None:
        self._stages.clear()


registry = PluginRegistry()
