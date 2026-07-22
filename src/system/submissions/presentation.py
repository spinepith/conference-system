from __future__ import annotations

from typing import Any

WARNING_CODE_LABELS = {
    "ambiguous_formulation": "Формулировки допускают неоднозначное толкование.",
    "conclusions_not_supported": "Выводы недостаточно подтверждены содержанием материала.",
    "critical_personal_data_leak": "Обнаружены признаки раскрытия критически важных персональных данных.",
    "discriminatory_content": "Обнаружены формулировки, которые могут носить дискриминационный характер.",
    "document_number": "В тексте обнаружен номер документа, требующий ручной проверки.",
    "excessive_cliches": "В тексте слишком много шаблонных и общих формулировок.",
    "excessive_unexplained_terminology": "Используется много терминов без необходимых пояснений.",
    "extremist_content": "Обнаружены фрагменты, которые требуют проверки на недопустимое содержание.",
    "generic_phrasing": "Формулировки слишком общие и недостаточно конкретные.",
    "harmful_instructions": "Обнаружены потенциально опасные инструкции, требующие ручной проверки.",
    "illegal_activity": "Обнаружены признаки описания или поощрения незаконной деятельности.",
    "illegal_activity_reference": "В тексте есть упоминание незаконной деятельности, требующее проверки.",
    "inappropriate_tone": "Стиль изложения не соответствует научному материалу.",
    "incoherent_or_random_text": "Текст выглядит несвязным или содержит случайные фрагменты.",
    "insufficient_text_for_analysis": "Недостаточно текста для полноценной автоматической проверки.",
    "internal_contradiction": "В материале обнаружены внутренние противоречия.",
    "lack_of_specificity": "Материалу не хватает конкретики.",
    "missing_critical_sections": "Отсутствуют обязательные разделы научного материала.",
    "missing_keywords": "В материале не найдены ключевые слова.",
    "multiple_personal_data_instances": "Обнаружено несколько фрагментов с возможными персональными данными.",
    "no_clear_purpose": "Цель работы не сформулирована ясно.",
    "no_conclusions": "В материале отсутствуют выводы.",
    "no_introduction": "В материале отсутствует введение.",
    "no_method_described": "Метод или подход к исследованию не описан.",
    "no_references": "Не найден список литературы или ссылки на использованные источники.",
    "no_research_object": "Не указан объект или предмет исследования.",
    "no_research_or_project_component": "Не выявлена исследовательская или проектная составляющая.",
    "no_result": "В материале не представлены результаты работы.",
    "no_results": "В материале не представлены результаты работы.",
    "no_scientific_structure": "Структура материала не соответствует научному тексту.",
    "non_scientific_style": "Стиль изложения недостаточно научный.",
    "offensive_content": "Обнаружены оскорбительные формулировки, требующие ручной проверки.",
    "poor_logical_flow": "Логика изложения нарушена или прослеживается недостаточно ясно.",
    "potential_personal_data": "В тексте могут содержаться персональные данные.",
    "potentially_sensitive_content": "Обнаружены потенциально чувствительные сведения.",
    "requires_manual_review": "Фрагмент требует обязательной ручной проверки редактором.",
    "section_mismatch": "Материал может не соответствовать выбранной секции конференции.",
    "sensitive_info": "В тексте могут содержаться чувствительные сведения.",
    "sensitive_topic": "Материал затрагивает чувствительную тему и требует ручной проверки.",
    "terminology_issues": "Есть замечания к использованию терминологии.",
    "title_content_mismatch": "Название материала не вполне соответствует его содержанию.",
    "topic_relevance_weak": "Тематическое соответствие конференции выражено слабо.",
    "topic_unrelated_to_conference": "Тематика материала не соответствует направлению конференции.",
    "unclear_data_status": "Неясно происхождение или статус использованных данных.",
    "unclear_formulations": "В тексте есть неясные формулировки.",
    "unclear_main_topic": "Основная тема материала сформулирована недостаточно ясно.",
    "weak_ai_connection": "Связь материала с тематикой искусственного интеллекта выражена недостаточно.",
    "weak_cohesion": "Связность текста недостаточна.",
    "weak_methodology": "Методика исследования описана недостаточно подробно.",
    "weak_paragraph_cohesion": "Связь между абзацами выражена недостаточно ясно.",
}

RISK_TYPE_LABELS = {
    "personal_data": "Персональные данные",
    "document_number": "Номер документа",
    "contact_data": "Контактные данные",
    "sensitive_topic": "Чувствительная тема",
    "harmful_instruction": "Опасная инструкция",
    "illegal_activity": "Незаконная деятельность",
    "discriminatory_content": "Дискриминационная формулировка",
    "offensive_content": "Оскорбительная формулировка",
}


def _value(check: Any, name: str, default: Any = "") -> Any:
    if isinstance(check, dict):
        return check.get(name, default)
    return getattr(check, name, default)


def looks_like_technical_code(value: str) -> bool:
    normalized = str(value or "").strip()
    return bool(normalized) and " " not in normalized and normalized.replace("_", "").isalnum()


def issue_text(item: Any, *, fallback: str = "") -> str:
    if isinstance(item, dict):
        code = str(item.get("code") or "").strip()
        message = str(item.get("message") or item.get("reason") or "").strip()
        recommendation = str(item.get("recommendation") or "").strip()
    else:
        code = ""
        message = str(item or "").strip()
        recommendation = ""

    if message and not looks_like_technical_code(message):
        return message
    technical_value = code or message
    if technical_value in WARNING_CODE_LABELS:
        return WARNING_CODE_LABELS[technical_value]
    if recommendation and not looks_like_technical_code(recommendation):
        return recommendation
    if fallback and not looks_like_technical_code(fallback):
        return fallback
    return "Автоматическая проверка отметила фрагмент, который требует ручной оценки."


def format_issues(items: Any, *, fallback: str = "") -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in items or []:
        source = item if isinstance(item, dict) else {}
        result.append(
            {
                "display_message": issue_text(item, fallback=fallback),
                "location": str(source.get("location") or "").strip(),
                "recommendation": str(source.get("recommendation") or "").strip(),
            }
        )
    return result


def format_flagged_fragments(items: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        risk_type = str(item.get("risk_type") or "").strip()
        result.append(
            {
                "fragment": str(item.get("fragment") or item.get("text") or "").strip(),
                "risk_type": RISK_TYPE_LABELS.get(risk_type, "Фрагмент для ручной проверки"),
                "reason": str(item.get("reason") or "").strip(),
                "recommendation": str(item.get("recommendation") or "").strip(),
            }
        )
    return result


def format_check(check: Any, *, audience: str) -> dict[str, Any]:
    summary = str(_value(check, "summary") or "").strip()
    audience_comment = str(
        _value(check, "editor_comment" if audience == "editor" else "author_comment") or ""
    ).strip()
    fallback = audience_comment or summary
    warnings = format_issues(_value(check, "warnings", []), fallback=fallback)
    errors = format_issues(_value(check, "errors", []), fallback=fallback)
    fragments = format_flagged_fragments(_value(check, "flagged_fragments", []))
    status = str(_value(check, "status") or "").strip()
    has_attention = status in {"warning", "failed", "error"} or bool(warnings or errors or fragments)
    return {
        "check_id": str(_value(check, "check_id") or ""),
        "title": str(_value(check, "title") or _value(check, "check_id") or "Автоматическая проверка"),
        "status": status,
        "risk_level": str(_value(check, "risk_level") or "low"),
        "score": _value(check, "score", None),
        "summary": summary,
        "audience_comment": audience_comment,
        "warnings_display": warnings,
        "errors_display": errors,
        "flagged_fragments_display": fragments,
        "has_attention": has_attention,
    }


def feedback_summary(checks: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for check in checks:
        if not check.get("has_attention"):
            continue
        candidates = [check.get("audience_comment"), check.get("summary")]
        candidates.extend(item.get("display_message") for item in check.get("warnings_display", []))
        candidates.extend(item.get("display_message") for item in check.get("errors_display", []))
        candidates.extend(item.get("reason") for item in check.get("flagged_fragments_display", []))
        for candidate in candidates:
            text = str(candidate or "").strip()
            if text and text not in lines:
                lines.append(text)
                if len(lines) >= limit:
                    return lines
    return lines
