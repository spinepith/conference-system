from abc import ABC, abstractmethod
from typing import Any


class BaseWorkflowStage(ABC):
    stage_id: str
    title: str
    description: str = ""
    enabled: bool = True

    @abstractmethod
    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        """Run processing stage and return a structured JSON-serializable result."""
        raise NotImplementedError
