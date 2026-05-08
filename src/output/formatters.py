"""Output formatters: convert AgentContext artifacts to Markdown, JSON, OpenAPI files."""

import json
from pathlib import Path
from datetime import datetime

from src.models.artifacts import AgentContext


class OutputWriter:
    """Writes all pipeline artifacts to a structured output directory."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.project_dir: Path | None = None

    def write_all(self, context: AgentContext) -> Path:
        """Write all artifacts. Returns the project output directory path."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = context.project_name.replace(" ", "_")[:50]
        self.project_dir = self.base_dir / f"{safe_name}_{ts}"
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self._write_user_stories(context)
        self._write_db_schema(context)
        self._write_api_contracts(context)
        self._write_code_artifacts(context)
        self._write_test_cases(context)
        self._write_review_report(context)
        self._write_openapi(context)
        self._write_tasks(context)
        self._write_summary(context)

        return self.project_dir

    def _write_file(self, filename: str, content: str):
        path = self.project_dir / filename
        path.write_text(content, encoding="utf-8")

    # ── Individual writers ───────────────────────────────────────────────

    def _write_user_stories(self, ctx: AgentContext):
        lines = [
            "# 产品需求分析 — 用户故事",
            f"\n> 项目: {ctx.project_name}",
            f"> 功能模块: {len(ctx.functional_modules)} 个",
            f"> 用户故事: {len(ctx.user_stories)} 个",
            f"> 生成时间: {datetime.now().isoformat()}",
            "\n---\n",
        ]

        # Functional modules
        lines.append("## 功能模块\n")
        for m in ctx.functional_modules:
            lines.append(f"### {m.name}")
            lines.append(f"{m.description}\n")
            if m.user_story_ids:
                lines.append(f"关联故事: {', '.join(m.user_story_ids)}\n")

        # User stories
        lines.append("---\n\n## 用户故事详情\n")
        for s in ctx.user_stories:
            lines.append(f"### {s.id}: {s.title}")
            lines.append(f"- **优先级**: {s.priority.value}")
            lines.append(f"- **作为**: {s.as_a}")
            lines.append(f"- **我想要**: {s.i_want}")
            lines.append(f"- **以便**: {s.so_that}")

            if s.acceptance_criteria:
                lines.append("\n**验收标准**:")
                for i, ac in enumerate(s.acceptance_criteria, 1):
                    lines.append(f"{i}. Given **{ac.given}**, When **{ac.when}**, Then **{ac.then}**")

            if s.boundary_conditions:
                lines.append("\n**边界条件**:")
                lines.append("| 场景 | 类别 | 输入条件 | 期望行为 |")
                lines.append("|------|------|----------|----------|")
                for bc in s.boundary_conditions:
                    lines.append(
                        f"| {bc.scenario} | {bc.category} | {bc.input_condition} | {bc.expected_behavior} |"
                    )

            lines.append("\n---\n")

        self._write_file("01_user_stories.md", "\n".join(lines))

    def _write_db_schema(self, ctx: AgentContext):
        lines = [
            "# 数据库设计",
            f"\n> 项目: {ctx.project_name}",
            f"> 数据表: {len(ctx.db_schema)} 个",
            "\n---\n",
        ]

        if ctx.tech_stack:
            lines.append("## 技术选型\n")
            lines.append(f"- **语言**: {ctx.tech_stack.language}")
            lines.append(f"- **框架**: {ctx.tech_stack.framework}")
            lines.append(f"- **ORM**: {ctx.tech_stack.orm}")
            lines.append(f"- **数据库**: {ctx.tech_stack.database}")
            if ctx.tech_stack.reasoning:
                lines.append(f"\n> {ctx.tech_stack.reasoning}")
            lines.append("\n---\n")

        lines.append("## 全部 DDL\n")
        for t in ctx.db_schema:
            if t.ddl:
                lines.append(f"```sql\n{t.ddl}\n```\n")

        lines.append("---\n\n## 表结构详情\n")
        for t in ctx.db_schema:
            lines.append(f"### {t.name}")
            if t.comment:
                lines.append(f"_{t.comment}_\n")
            lines.append("| 列名 | 类型 | 可空 | 主键 | 唯一 | 默认值 | 说明 |")
            lines.append("|------|------|------|------|------|--------|------|")
            for c in t.columns:
                pk = "Y" if c.primary_key else ""
                uq = "Y" if c.unique else ""
                nullable = "Y" if c.nullable else "N"
                default = c.default or ""
                lines.append(f"| {c.name} | {c.type} | {nullable} | {pk} | {uq} | {default} | {c.comment} |")

            if t.indexes:
                lines.append(f"\n**索引**: {', '.join(f'{i.name}({",".join(i.columns)})' for i in t.indexes)}")
            lines.append("")

        self._write_file("02_database_schema.md", "\n".join(lines))

    def _write_api_contracts(self, ctx: AgentContext):
        lines = [
            "# API 接口契约",
            f"\n> 项目: {ctx.project_name}",
            f"> API 端点: {len(ctx.api_contracts)} 个",
            "\n---\n",
        ]

        # Group by tag
        tags: dict[str, list] = {}
        for a in ctx.api_contracts:
            for tag in a.tags or ["Default"]:
                tags.setdefault(tag, []).append(a)

        for tag, apis in tags.items():
            lines.append(f"## {tag}\n")
            for api in apis:
                lines.append(f"### {api.method.value} {api.path}")
                lines.append(f"**{api.summary}**\n")
                if api.description:
                    lines.append(f"{api.description}\n")

                if api.path_params:
                    lines.append("**路径参数**:")
                    lines.append("| 名称 | 类型 | 必填 | 说明 |")
                    lines.append("|------|------|------|------|")
                    for p in api.path_params:
                        lines.append(f"| {p.name} | {p.type} | {'Y' if p.required else 'N'} | {p.description} |")
                    lines.append("")

                if api.query_params:
                    lines.append("**查询参数**:")
                    lines.append("| 名称 | 类型 | 必填 | 说明 |")
                    lines.append("|------|------|------|------|")
                    for p in api.query_params:
                        lines.append(f"| {p.name} | {p.type} | {'Y' if p.required else 'N'} | {p.description} |")
                    lines.append("")

                if api.request_body_schema:
                    lines.append(f"**请求体**:\n```json\n{api.request_body_schema}\n```\n")
                if api.response_schema:
                    lines.append(f"**响应体**:\n```json\n{api.response_schema}\n```\n")

                lines.append("---\n")

        self._write_file("03_api_contracts.md", "\n".join(lines))

    def _write_code_artifacts(self, ctx: AgentContext):
        code_dir = self.project_dir / "code"
        code_dir.mkdir(exist_ok=True)

        lines = [
            "# 代码骨架",
            f"\n> 项目: {ctx.project_name}",
            f"> 代码文件: {len(ctx.code_artifacts)} 个",
            "\n---\n",
        ]

        for c in ctx.code_artifacts:
            # Write individual code file
            file_path = code_dir / c.file_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(c.content, encoding="utf-8")

            lines.append(f"### {c.file_path}")
            if c.description:
                lines.append(f"_{c.description}_")
            lines.append(f"\n```{c.language}\n{c.content}\n```\n")
            lines.append("---\n")

        self._write_file("04_code_artifacts.md", "\n".join(lines))

    def _write_test_cases(self, ctx: AgentContext):
        lines = [
            "# 测试用例",
            f"\n> 项目: {ctx.project_name}",
            f"> 测试用例: {len(ctx.test_cases)} 个",
            "\n---\n",
        ]

        for test_type in ["unit", "integration", "boundary"]:
            type_cases = [tc for tc in ctx.test_cases if tc.type.value == test_type]
            if not type_cases:
                continue

            lines.append(f"## {test_type.upper()} 测试\n")

            for tc in type_cases:
                lines.append(f"### {tc.id}: {tc.title}")
                if tc.description:
                    lines.append(f"\n{tc.description}\n")
                lines.append(f"- **类型**: {tc.type.value}")
                if tc.related_api:
                    lines.append(f"- **关联 API**: {tc.related_api}")
                if tc.related_user_story:
                    lines.append(f"- **关联故事**: {tc.related_user_story}")

                if tc.setup:
                    lines.append("\n**前置准备**:")
                    for s in tc.setup:
                        lines.append(f"- {s}")

                if tc.steps:
                    lines.append("\n**测试步骤**:")
                    for i, s in enumerate(tc.steps, 1):
                        lines.append(f"{i}. {s}")

                lines.append(f"\n**期望结果**: {tc.expected_result}")

                if tc.test_data:
                    lines.append(f"\n**测试数据**:\n```json\n{tc.test_data}\n```")

                if tc.code:
                    lines.append(f"\n**测试代码**:\n```java\n{tc.code}\n```")

                lines.append("\n---\n")

        self._write_file("05_test_cases.md", "\n".join(lines))

    def _write_review_report(self, ctx: AgentContext):
        if not ctx.review_report:
            return

        report = ctx.review_report
        lines = [
            "# 审查报告",
            f"\n> 项目: {ctx.project_name}",
            f"> 一致性问题: {len(report.consistency_issues)} 个",
            "\n---\n",
        ]

        lines.append(f"## 摘要\n\n{report.summary}\n")

        if report.consistency_issues:
            lines.append("---\n\n## 一致性问题\n")
            lines.append("| 严重度 | 类别 | 位置 | 详情 | 建议 |")
            lines.append("|--------|------|------|------|------|")
            for issue in report.consistency_issues:
                lines.append(
                    f"| {issue.severity} | {issue.category} | {issue.location} | {issue.detail} | {issue.suggestion} |"
                )

        # Summary counts
        errors = sum(1 for i in report.consistency_issues if i.severity == "error")
        warnings = sum(1 for i in report.consistency_issues if i.severity == "warning")
        infos = sum(1 for i in report.consistency_issues if i.severity == "info")
        lines.append(f"\n> 错误: {errors} | 警告: {warnings} | 信息: {infos}")

        self._write_file("06_review_report.md", "\n".join(lines))

    def _write_openapi(self, ctx: AgentContext):
        if not ctx.review_report or not ctx.review_report.openapi_spec:
            # Generate a basic one from API contracts
            spec = self._generate_openapi(ctx)
            self._write_file("openapi.yaml", spec)
        else:
            self._write_file("openapi.yaml", ctx.review_report.openapi_spec)

    def _write_tasks(self, ctx: AgentContext):
        if not ctx.review_report or not ctx.review_report.tasks:
            return

        tasks = ctx.review_report.tasks
        lines = [
            "# 开发任务拆分",
            f"\n> 项目: {ctx.project_name}",
            f"> 任务总数: {len(tasks)}",
            f"> 预估总工时: {sum(t.estimated_hours for t in tasks):.1f}h",
            "\n---\n",
        ]

        by_phase: dict[str, list] = {}
        for t in tasks:
            by_phase.setdefault(t.assigned_phase or "other", []).append(t)

        for phase, phase_tasks in by_phase.items():
            lines.append(f"## {phase.upper()}\n")
            lines.append("| ID | 标题 | 优先级 | 预估(h) | 依赖 |")
            lines.append("|----|------|--------|---------|------|")
            for t in phase_tasks:
                deps = ", ".join(t.depends_on) if t.depends_on else "-"
                lines.append(f"| {t.id} | {t.title} | {t.priority.value} | {t.estimated_hours} | {deps} |")
            lines.append("")

            # Detailed tasks
            for t in phase_tasks:
                if t.description:
                    lines.append(f"### {t.id}: {t.title}\n{t.description}\n")

        self._write_file("07_task_breakdown.md", "\n".join(lines))

    def _write_summary(self, ctx: AgentContext):
        """Write a JSON summary of the full context for tool consumption."""
        self._write_file("full_context.json", ctx.model_dump_json(indent=2))

    def _generate_openapi(self, ctx: AgentContext) -> str:
        """Generate a basic OpenAPI 3.0 spec from API contracts when reviewer doesn't provide one."""
        paths = {}
        for api in ctx.api_contracts:
            path_item = paths.setdefault(api.path, {})
            method = api.method.value.lower()
            operation = {
                "summary": api.summary,
                "description": api.description,
                "tags": api.tags,
                "operationId": f"{method}_{api.path.replace('/', '_').replace('{', '').replace('}', '')}",
                "responses": {
                    "200": {"description": "Success"},
                    "400": {"description": "Bad Request"},
                    "500": {"description": "Internal Server Error"},
                },
            }
            if api.request_body_schema:
                try:
                    operation["requestBody"] = {
                        "content": {"application/json": {"schema": json.loads(api.request_body_schema)}}
                    }
                except json.JSONDecodeError:
                    operation["requestBody"] = {"content": {"application/json": {}}}
            path_item[method] = operation

        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": f"{ctx.project_name} API",
                "version": "1.0.0",
                "description": f"Auto-generated API for {ctx.project_name}",
            },
            "paths": paths,
        }
        return json.dumps(spec, indent=2, ensure_ascii=False)
