"""Agent 3a: Backend Developer — API + DB → Code Skeletons."""

import json

from src.agents.base import BaseAgent
from src.models.artifacts import AgentContext, CodeFile
from src.prompts.templates import BACKEND_DEV_PROMPT


class BackendDeveloper(BaseAgent):
    role_name = "backend-developer"
    system_prompt = BACKEND_DEV_PROMPT

    def run(self, context: AgentContext) -> AgentContext:
        user_msg, system_prompt = self._build_message(context)
        data = self._call_json(user_msg, system_prompt=system_prompt)

        context.code_artifacts = [
            CodeFile(
                file_path=c["file_path"],
                language=c.get("language", "java"),
                content=c["content"],
                description=c.get("description", ""),
            )
            for c in data.get("code_artifacts", [])
        ]

        return context

    def _build_message(self, context: AgentContext) -> tuple[str, str]:
        tech = "Spring Boot 3 + Java 17"
        if context.tech_stack:
            tech = f"{context.tech_stack.framework} + {context.tech_stack.language}"

        # Inject tech stack into prompt
        system_prompt = self.system_prompt.replace("{tech_stack}", tech)

        # Build a compact representation of DB schema and API contracts
        db_json = json.dumps(
            [
                {
                    "name": t.name,
                    "comment": t.comment,
                    "columns": [
                        {"name": c.name, "type": c.type, "nullable": c.nullable, "comment": c.comment}
                        for c in t.columns
                    ],
                    "ddl": t.ddl,
                }
                for t in context.db_schema
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
                    "query_params": [{"name": p.name, "type": p.type, "required": p.required} for p in a.query_params],
                }
                for a in context.api_contracts
            ],
            ensure_ascii=False,
            indent=2,
        )

        user_msg = f"""Generate backend code skeletons based on the following design.

Project: {context.project_name}
Tech Stack: {tech}

Database Schema:
{db_json}

API Contracts:
{api_json}

Generate DTOs, Controllers, Services, and Repositories for all API endpoints. Use the system prompt instructions for format and conventions."""
        return user_msg, system_prompt
