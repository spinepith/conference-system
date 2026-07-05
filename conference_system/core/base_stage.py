from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseWorkflowStage(ABC):
    """Base class for pluggable workflow stages."""

    stage_id: str
    title: str
    description: str = ""
    enabled: bool = True

    @abstractmethod
    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        """Run stage and return structured result."""
        raise NotImplementedError
