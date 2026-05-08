"""Pydantic models for inter-agent communication artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Product Analyst outputs ──────────────────────────────────────────────

class StoryPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class AcceptanceCriterion(BaseModel):
    given: str
    when: str
    then: str


class BoundaryCondition(BaseModel):
    scenario: str
    input_condition: str
    expected_behavior: str
    category: str  # normal / edge / exception


class UserStory(BaseModel):
    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    priority: StoryPriority = StoryPriority.P2
    acceptance_criteria: list[AcceptanceCriterion] = []
    boundary_conditions: list[BoundaryCondition] = []


class FunctionalModule(BaseModel):
    name: str
    description: str
    user_story_ids: list[str] = []


# ── Architect outputs ────────────────────────────────────────────────────

class ColumnDef(BaseModel):
    name: str
    type: str
    nullable: bool = False
    primary_key: bool = False
    unique: bool = False
    default: Optional[str] = None
    comment: str = ""


class IndexDef(BaseModel):
    name: str
    columns: list[str]
    unique: bool = False


class TableDef(BaseModel):
    name: str
    comment: str = ""
    columns: list[ColumnDef] = []
    indexes: list[IndexDef] = []
    ddl: str = ""


class ApiMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ApiParam(BaseModel):
    name: str
    in_: str = Field(alias="in")
    type: str
    required: bool = False
    description: str = ""


class ApiResponse(BaseModel):
    status_code: int
    description: str
    schema_ref: str = ""


class APIEndpoint(BaseModel):
    path: str
    method: ApiMethod
    summary: str
    description: str = ""
    tags: list[str] = []
    request_body_schema: Optional[str] = None  # JSON Schema string
    response_schema: Optional[str] = None      # JSON Schema string
    query_params: list[ApiParam] = []
    path_params: list[ApiParam] = []


class ModuleDesign(BaseModel):
    name: str
    description: str
    responsibilities: list[str] = []
    tables: list[str] = []
    apis: list[str] = []
    dependencies: list[str] = []


class TechStackRecommendation(BaseModel):
    language: str
    framework: str
    orm: str
    database: str
    reasoning: str = ""


# ── Backend Developer outputs ────────────────────────────────────────────

class CodeFile(BaseModel):
    file_path: str
    language: str
    content: str
    description: str = ""


# ── Test Engineer outputs ────────────────────────────────────────────────

class TestType(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    BOUNDARY = "boundary"


class TestCase(BaseModel):
    id: str
    title: str
    type: TestType
    description: str = ""
    setup: list[str] = []
    steps: list[str] = []
    expected_result: str = ""
    related_api: Optional[str] = None
    related_user_story: Optional[str] = None
    test_data: Optional[str] = None
    code: str = ""


# ── Reviewer outputs ─────────────────────────────────────────────────────

class ConsistencyIssue(BaseModel):
    severity: str  # error / warning / info
    category: str  # field-mismatch / missing / extra / naming
    location: str  # e.g. "API POST /users vs Table users"
    detail: str
    suggestion: str = ""


class TaskItem(BaseModel):
    id: str
    title: str
    description: str = ""
    priority: StoryPriority = StoryPriority.P2
    estimated_hours: float = 0
    depends_on: list[str] = []
    assigned_phase: str = ""  # backend / frontend / testing / devops


class ReviewReport(BaseModel):
    consistency_issues: list[ConsistencyIssue] = []
    openapi_spec: str = ""  # OpenAPI 3.0 YAML/JSON string
    tasks: list[TaskItem] = []
    summary: str = ""


# ── Unified Agent Context ────────────────────────────────────────────────

class AgentContext(BaseModel):
    prd_raw: str = ""
    project_name: str = ""

    # Phase 1 outputs
    functional_modules: list[FunctionalModule] = []
    user_stories: list[UserStory] = []

    # Phase 2 outputs
    module_designs: list[ModuleDesign] = []
    db_schema: list[TableDef] = []
    api_contracts: list[APIEndpoint] = []
    tech_stack: Optional[TechStackRecommendation] = None

    # Phase 3a outputs
    code_artifacts: list[CodeFile] = []

    # Phase 3b outputs
    test_cases: list[TestCase] = []

    # Phase 4 outputs
    review_report: Optional[ReviewReport] = None

    def summary(self) -> str:
        parts = [f"Project: {self.project_name}"]
        if self.functional_modules:
            parts.append(f"Modules: {len(self.functional_modules)}")
        if self.user_stories:
            parts.append(f"User Stories: {len(self.user_stories)}")
        if self.db_schema:
            parts.append(f"Tables: {len(self.db_schema)}")
        if self.api_contracts:
            parts.append(f"APIs: {len(self.api_contracts)}")
        if self.code_artifacts:
            parts.append(f"Code Files: {len(self.code_artifacts)}")
        if self.test_cases:
            parts.append(f"Test Cases: {len(self.test_cases)}")
        if self.review_report:
            issues = len(self.review_report.consistency_issues)
            parts.append(f"Issues: {issues}")
        return " | ".join(parts)
