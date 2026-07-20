from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IssueCreate:
    issue_id: str
    title: str
    year: int
    quarter: int
    conference_id: str = "ai_quarterly_conf"
    org_committee: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if len(self.issue_id.strip()) < 2:
            raise ValueError("Идентификатор выпуска слишком короткий.")
        if len(self.title.strip()) < 2:
            raise ValueError("Название выпуска слишком короткое.")
        if not 2000 <= int(self.year) <= 2100:
            raise ValueError("Год выпуска должен быть от 2000 до 2100.")
        if int(self.quarter) not in {1, 2, 3, 4}:
            raise ValueError("Квартал должен быть от 1 до 4.")

    def to_dict(self) -> dict:
        self.validate()
        return {
            "issue_id": self.issue_id.strip(),
            "conference_id": self.conference_id,
            "title": self.title.strip(),
            "year": int(self.year),
            "quarter": int(self.quarter),
            "org_committee": list(self.org_committee),
        }
