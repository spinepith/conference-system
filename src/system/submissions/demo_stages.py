from typing import Any

from .base_stage import BaseWorkflowStage
from .plugin_registry import registry


class DemoMetadataStage(BaseWorkflowStage):
    stage_id = "extract_metadata_demo"
    title = "Демонстрационное извлечение метаданных"
    description = "Заглушка для интеграции с модулем DOCX-извлечения."

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "success",
            "message": "Демо-этап: заявка доступна для DOCX-обработчика.",
            "submission_id": submission["submission_id"],
        }


class DemoChecksStage(BaseWorkflowStage):
    stage_id = "auto_checks_demo"
    title = "Демонстрационная автоматическая проверка"
    description = "Заглушка для интеграции с модулем автоматических проверок."

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "warning",
            "message": "Демо-этап: реальный модуль проверок должен записать CheckResult.",
            "risk_level": "low",
        }


def register_demo_stages() -> None:
    if registry.list():
        return
    registry.register(DemoMetadataStage())
    registry.register(DemoChecksStage())
