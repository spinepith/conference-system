from __future__ import annotations

from typing import Any

from conference_system.core.base_stage import BaseWorkflowStage
from conference_system.core.plugin_registry import registry


class IntakeValidationStage(BaseWorkflowStage):
    stage_id = "intake_validation"
    title = "Проверка заявки"
    description = "Проверяет наличие базовых данных заявки."

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        warnings = []
        metadata = submission.get("metadata", {}) or {}
        contact = submission.get("author_contact", {}) or {}
        if not metadata.get("title_ru"):
            warnings.append("Не указано название материала.")
        if not contact.get("email"):
            warnings.append("Не указан e-mail контактного автора.")
        return {
            "status": "warning" if warnings else "success",
            "message": "Есть предупреждения" if warnings else "Базовая заявка заполнена",
            "warnings": warnings,
        }


class WaitingExternalModulesStage(BaseWorkflowStage):
    stage_id = "waiting_external_modules"
    title = "Ожидание внешних модулей"
    description = "Фиксирует, что дальнейшие этапы выполняются другими студентами."

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "skipped",
            "message": "DOCX-извлечение, оформление, проверки и PDF выполняются отдельными модулями.",
            "next_modules": [
                "docx_extraction",
                "template_formatting",
                "automatic_checks",
                "pdf_export",
            ],
        }


def register_demo_stages() -> None:
    for stage_cls in (IntakeValidationStage, WaitingExternalModulesStage):
        stage = stage_cls()
        try:
            registry.register(stage)
        except ValueError:
            pass
