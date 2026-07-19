from __future__ import annotations

from .base_stage import BaseWorkflowStage


class PluginRegistry:
    def __init__(self) -> None:
        self._stages: dict[str, BaseWorkflowStage] = {}

    def register(self, stage: BaseWorkflowStage) -> None:
        if not stage.stage_id:
            raise ValueError("Workflow stage must have stage_id")
        self._stages[stage.stage_id] = stage

    def get(self, stage_id: str) -> BaseWorkflowStage:
        return self._stages[stage_id]

    def list(self) -> list[BaseWorkflowStage]:
        return list(self._stages.values())

    def clear(self) -> None:
        self._stages.clear()


registry = PluginRegistry()
