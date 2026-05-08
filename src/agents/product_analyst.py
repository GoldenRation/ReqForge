"""Agent 1: Product Analyst — PRD → User Stories, Modules, Boundary Conditions."""

from src.agents.base import BaseAgent
from src.models.artifacts import (
    AgentContext,
    FunctionalModule,
    UserStory,
    AcceptanceCriterion,
    BoundaryCondition,
    StoryPriority,
)
from src.prompts.templates import PRODUCT_ANALYST_PROMPT


class ProductAnalyst(BaseAgent):
    role_name = "product-analyst"
    system_prompt = PRODUCT_ANALYST_PROMPT

    def run(self, context: AgentContext) -> AgentContext:
        user_msg = self._build_message(context)
        data = self._call_json(user_msg)

        # Parse functional modules
        context.functional_modules = [
            FunctionalModule(
                name=m["name"],
                description=m.get("description", ""),
                user_story_ids=m.get("user_story_ids", []),
            )
            for m in data.get("functional_modules", [])
        ]

        # Parse user stories
        context.user_stories = []
        for s in data.get("user_stories", []):
            story = UserStory(
                id=s["id"],
                title=s["title"],
                as_a=s.get("as_a", ""),
                i_want=s.get("i_want", ""),
                so_that=s.get("so_that", ""),
                priority=StoryPriority(s.get("priority", "P2")),
                acceptance_criteria=[
                    AcceptanceCriterion(
                        given=ac.get("given", ""),
                        when=ac.get("when", ""),
                        then=ac.get("then", ""),
                    )
                    for ac in s.get("acceptance_criteria", [])
                ],
                boundary_conditions=[
                    BoundaryCondition(
                        scenario=bc.get("scenario", ""),
                        input_condition=bc.get("input_condition", ""),
                        expected_behavior=bc.get("expected_behavior", ""),
                        category=bc.get("category", "normal"),
                    )
                    for bc in s.get("boundary_conditions", [])
                ],
            )
            context.user_stories.append(story)

        return context

    def _build_message(self, context: AgentContext) -> str:
        return f"""Analyze the following PRD / requirements document and extract structured analysis.

Project Name: {context.project_name}

PRD Content:
---
{context.prd_raw}
---

Identify all user stories with acceptance criteria and boundary conditions (normal flow, edge cases, exception flows). Group them into functional modules."""
