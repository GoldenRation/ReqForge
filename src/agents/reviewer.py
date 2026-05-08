"""Agent 4: Reviewer — Cross-artifact consistency check, OpenAPI docs, task breakdown."""

import json

from src.agents.base import BaseAgent
from src.models.artifacts import (
    AgentContext,
    ConsistencyIssue,
    TaskItem,
    ReviewReport,
    StoryPriority,
)
from src.prompts.templates import REVIEWER_PROMPT


class Reviewer(BaseAgent):
    role_name = "reviewer"
    system_prompt = REVIEWER_PROMPT

    def run(self, context: AgentContext) -> AgentContext:
        user_msg = self._build_message(context)
        data = self._call_json(user_msg)

        issues = [
            ConsistencyIssue(
                severity=i.get("severity", "info"),
                category=i.get("category", ""),
                location=i.get("location", ""),
                detail=i.get("detail", ""),
                suggestion=i.get("suggestion", ""),
            )
            for i in data.get("consistency_issues", [])
        ]

        tasks = [
            TaskItem(
                id=t["id"],
                title=t["title"],
                description=t.get("description", ""),
                priority=StoryPriority(t.get("priority", "P2")),
                estimated_hours=t.get("estimated_hours", 0),
                depends_on=t.get("depends_on", []),
                assigned_phase=t.get("assigned_phase", "backend"),
            )
            for t in data.get("tasks", [])
        ]

        context.review_report = ReviewReport(
            consistency_issues=issues,
            openapi_spec=data.get("openapi_spec", ""),
            tasks=tasks,
            summary=data.get("summary", ""),
        )

        return context

    def _build_message(self, context: AgentContext) -> str:
        # Build a comprehensive snapshot of all artifacts
        snapshot = {
            "project": context.project_name,
            "functional_modules": [
                {"name": m.name, "description": m.description} for m in context.functional_modules
            ],
            "user_stories": [
                {
                    "id": s.id,
                    "title": s.title,
                    "as_a": s.as_a,
                    "i_want": s.i_want,
                    "so_that": s.so_that,
                    "boundary_conditions": [
                        {"scenario": bc.scenario, "category": bc.category} for bc in s.boundary_conditions
                    ],
                }
                for s in context.user_stories
            ],
            "db_schema": [
                {
                    "name": t.name,
                    "columns": [{"name": c.name, "type": c.type, "nullable": c.nullable} for c in t.columns],
                }
                for t in context.db_schema
            ],
            "api_contracts": [
                {
                    "path": a.path,
                    "method": a.method.value,
                    "summary": a.summary,
                    "request_body_schema": a.request_body_schema,
                    "response_schema": a.response_schema,
                }
                for a in context.api_contracts
            ],
            "code_artifacts": [
                {"file_path": c.file_path, "language": c.language, "description": c.description}
                for c in context.code_artifacts
            ],
            "test_cases": [
                {"id": tc.id, "title": tc.title, "type": tc.type.value, "related_api": tc.related_api}
                for tc in context.test_cases
            ],
        }

        return f"""Review ALL the following artifacts for consistency and generate the final deliverables.

All Artifacts (JSON):
{json.dumps(snapshot, ensure_ascii=False, indent=2)}

Perform the following checks:
1. Cross-reference API request/response fields with database table columns — flag mismatches
2. Verify every user story has corresponding API endpoints
3. Verify every data-persisting API has a database table
4. Check naming consistency across all artifacts
5. Check type consistency (DB column types vs API field types)

Then generate:
- A list of all consistency issues found
- A complete OpenAPI 3.0 YAML specification
- A prioritized task breakdown for implementation"""
