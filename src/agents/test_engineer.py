"""Agent 3b: Test Engineer — User Stories + API → Test Cases."""

import json

from src.agents.base import BaseAgent
from src.models.artifacts import AgentContext, TestCase, TestType
from src.prompts.templates import TEST_ENGINEER_PROMPT


class TestEngineer(BaseAgent):
    role_name = "test-engineer"
    system_prompt = TEST_ENGINEER_PROMPT

    def run(self, context: AgentContext) -> AgentContext:
        user_msg = self._build_message(context)
        data = self._call_json(user_msg)

        context.test_cases = []
        for tc in data.get("test_cases", []):
            test_case = TestCase(
                id=tc["id"],
                title=tc["title"],
                type=TestType(tc.get("type", "unit")),
                description=tc.get("description", ""),
                setup=tc.get("setup", []),
                steps=tc.get("steps", []),
                expected_result=tc.get("expected_result", ""),
                related_api=tc.get("related_api"),
                related_user_story=tc.get("related_user_story"),
                test_data=tc.get("test_data"),
                code=tc.get("code", ""),
            )
            context.test_cases.append(test_case)

        return context

    def _build_message(self, context: AgentContext) -> str:
        stories_json = json.dumps(
            [
                {
                    "id": s.id,
                    "title": s.title,
                    "as_a": s.as_a,
                    "i_want": s.i_want,
                    "so_that": s.so_that,
                    "acceptance_criteria": [
                        {"given": ac.given, "when": ac.when, "then": ac.then}
                        for ac in s.acceptance_criteria
                    ],
                    "boundary_conditions": [
                        {"scenario": bc.scenario, "category": bc.category, "input_condition": bc.input_condition}
                        for bc in s.boundary_conditions
                    ],
                }
                for s in context.user_stories
            ],
            ensure_ascii=False,
            indent=2,
        )

        api_json = json.dumps(
            [
                {
                    "path": a.path,
                    "method": a.method.value,
                    "summary": a.summary,
                    "request_body_schema": a.request_body_schema,
                    "response_schema": a.response_schema,
                }
                for a in context.api_contracts
            ],
            ensure_ascii=False,
            indent=2,
        )

        return f"""Generate comprehensive test cases based on the following analysis and API design.

Project: {context.project_name}

User Stories:
{stories_json}

API Contracts:
{api_json}

Generate unit tests, integration tests, and boundary/edge-case tests. Cover all user story acceptance criteria and boundary conditions."""
