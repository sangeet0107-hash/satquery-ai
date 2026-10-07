"""
Routing layer (proposal section 5.2).

A Router turns the user's query (plus ingestion context) into a
RoutingDecision. RuleRouter wraps the existing keyword classifier. An
LLM-backed router can implement the same Router protocol later without
any change to the controller.
"""

from typing import Protocol

from pydantic import BaseModel

from backend.app.controller.classifier import classify_query
from backend.app.ingestion.info import RasterInfo
from backend.app.models.query import TaskType


class RoutingDecision(BaseModel):
    task: TaskType
    router: str
    rationale: str


class Router(Protocol):
    def route(
        self,
        query: str,
        infos: list[RasterInfo],
    ) -> RoutingDecision: ...


class RuleRouter:
    name = "rule-based"

    def route(self, query: str, infos: list[RasterInfo]) -> RoutingDecision:
        task = classify_query(query)

        return RoutingDecision(
            task=task,
            router=self.name,
            rationale=f"keyword rules matched task {task.value}",
        )
