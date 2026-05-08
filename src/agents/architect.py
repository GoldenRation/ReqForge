"""Agent 2: Architect — User Stories → DB Schema, API Contracts, Module Design."""

import json

from src.agents.base import BaseAgent
from src.models.artifacts import (
    AgentContext,
    ModuleDesign,
    TableDef,
    ColumnDef,
    IndexDef,
    APIEndpoint,
    ApiMethod,
    ApiParam,
    TechStackRecommendation,
)
from src.prompts.templates import ARCHITECT_PROMPT


class Architect(BaseAgent):
    role_name = "architect"
    system_prompt = ARCHITECT_PROMPT

    def run(self, context: AgentContext) -> AgentContext:
        user_msg = self._build_message(context)
        data = self._call_json(user_msg)

        # Parse tech stack
        ts = data.get("tech_stack", {})
        context.tech_stack = TechStackRecommendation(
            language=ts.get("language", "Java"),
            framework=ts.get("framework", "Spring Boot"),
            orm=ts.get("orm", "JPA"),
            database=ts.get("database", "MySQL"),
            reasoning=ts.get("reasoning", ""),
        )

        # Parse module designs
        context.module_designs = [
            ModuleDesign(
                name=m["name"],
                description=m.get("description", ""),
                responsibilities=m.get("responsibilities", []),
                tables=m.get("tables", []),
                apis=m.get("apis", []),
                dependencies=m.get("dependencies", []),
            )
            for m in data.get("module_designs", [])
        ]

        # Parse DB schema
        context.db_schema = []
        for t in data.get("db_schema", []):
            table = TableDef(
                name=t["name"],
                comment=t.get("comment", ""),
                columns=[
                    ColumnDef(
                        name=c["name"],
                        type=c["type"],
                        nullable=c.get("nullable", False),
                        primary_key=c.get("primary_key", False),
                        unique=c.get("unique", False),
                        default=c.get("default"),
                        comment=c.get("comment", ""),
                    )
                    for c in t.get("columns", [])
                ],
                indexes=[
                    IndexDef(
                        name=i["name"],
                        columns=i.get("columns", []),
                        unique=i.get("unique", False),
                    )
                    for i in t.get("indexes", [])
                ],
                ddl=t.get("ddl", ""),
            )
            context.db_schema.append(table)

        # Parse API contracts
        context.api_contracts = []
        for a in data.get("api_contracts", []):
            endpoint = APIEndpoint(
                path=a["path"],
                method=ApiMethod(a["method"]),
                summary=a.get("summary", ""),
                description=a.get("description", ""),
                tags=a.get("tags", []),
                query_params=[
                    ApiParam(
                        name=p["name"],
                        type=p.get("type", "string"),
                        required=p.get("required", False),
                        description=p.get("description", ""),
                        **{"in": p.get("in", "query")},
                    )
                    for p in a.get("query_params", [])
                ],
                path_params=[
                    ApiParam(
                        name=p["name"],
                        type=p.get("type", "string"),
                        required=p.get("required", False),
                        description=p.get("description", ""),
                        **{"in": p.get("in", "path")},
                    )
                    for p in a.get("path_params", [])
                ],
                request_body_schema=a.get("request_body_schema"),
                response_schema=a.get("response_schema"),
            )
            context.api_contracts.append(endpoint)

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
                    "priority": s.priority.value,
                    "acceptance_criteria": [
                        {"given": ac.given, "when": ac.when, "then": ac.then}
                        for ac in s.acceptance_criteria
                    ],
                    "boundary_conditions": [
                        {
                            "scenario": bc.scenario,
                            "category": bc.category,
                            "input_condition": bc.input_condition,
                            "expected_behavior": bc.expected_behavior,
                        }
                        for bc in s.boundary_conditions
                    ],
                }
                for s in context.user_stories
            ],
            ensure_ascii=False,
            indent=2,
        )

        modules_json = json.dumps(
            [
                {"name": m.name, "description": m.description, "user_story_ids": m.user_story_ids}
                for m in context.functional_modules
            ],
            ensure_ascii=False,
            indent=2,
        )

        return f"""Design the technical architecture based on the following analysis.

Project Name: {context.project_name}

Functional Modules:
{modules_json}

User Stories:
{stories_json}

Design the database schema (all tables with columns, types, indexes), REST API contracts (all endpoints with request/response schemas), and module boundaries."""
