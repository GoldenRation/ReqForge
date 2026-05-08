"""CLI entry point for the Requirements-to-Code Agent system."""

import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.markdown import Markdown

from src.models.artifacts import AgentContext
from src.orchestrator.pipeline import Pipeline, PipelineProgress
from src.output.formatters import OutputWriter
from src.config import OUTPUT_DIR


console = Console()


class RichProgress(PipelineProgress):
    """Pipeline progress rendered via Rich."""

    def __init__(self, progress: Progress, task_id):
        self.progress = progress
        self.task_id = task_id
        self._phase_count = 0

    def on_phase_start(self, phase: str, agent_name: str):
        self._phase_count += 1
        self.progress.update(
            self.task_id,
            description=f"[bold cyan]{phase}[/] {agent_name}",
            completed=self._phase_count - 1,
            total=6,  # 4 phases + start + finish
        )

    def on_phase_end(self, phase: str, agent_name: str, duration_ms: float):
        console.print(
            f"  [green][OK][/] {agent_name} — {duration_ms/1000:.1f}s"
        )

    def on_error(self, phase: str, error: str):
        console.print(f"  [red][FAIL][/] {phase} failed: {error}")


def print_banner():
    console.print(
        Panel.fit(
            "[bold blue]需求到代码 Agent[/]\n"
            "[dim]PRD → 用户故事 → 数据库 → API → 代码 → 测试 → 审查[/]",
            border_style="blue",
        )
    )


def print_context_summary(ctx: AgentContext):
    """Print a summary table of all generated artifacts."""
    console.print("\n[bold]生成产物总览[/]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("阶段")
    table.add_column("产物")
    table.add_column("数量")
    table.add_column("状态")

    def status_icon(count):
        return "[green][OK][/]" if count > 0 else "[dim]-[/]"

    table.add_row("Phase 1", "功能模块", str(len(ctx.functional_modules)), status_icon(len(ctx.functional_modules)))
    table.add_row("Phase 1", "用户故事", str(len(ctx.user_stories)), status_icon(len(ctx.user_stories)))
    table.add_row("Phase 2", "数据表", str(len(ctx.db_schema)), status_icon(len(ctx.db_schema)))
    table.add_row("Phase 2", "API 端点", str(len(ctx.api_contracts)), status_icon(len(ctx.api_contracts)))
    table.add_row("Phase 3a", "代码文件", str(len(ctx.code_artifacts)), status_icon(len(ctx.code_artifacts)))
    table.add_row("Phase 3b", "测试用例", str(len(ctx.test_cases)), status_icon(len(ctx.test_cases)))

    if ctx.review_report:
        issues = len(ctx.review_report.consistency_issues)
        tasks = len(ctx.review_report.tasks)
        issues_status = f"[yellow]{issues} 个问题[/]" if issues > 0 else "[green]无问题[/]"
        table.add_row("Phase 4", "一致性问题", str(issues), issues_status)
        table.add_row("Phase 4", "开发任务", str(tasks), status_icon(tasks))

    console.print(table)


@click.group()
@click.version_option(version="1.0.0")
def main():
    """需求到代码 Agent — 从 PRD 自动生成技术方案、数据库、API、代码和测试"""
    pass


@main.command()
@click.argument("prd_file", type=click.Path(exists=True))
@click.option("--name", "-n", default="Unnamed Project", help="项目名称")
@click.option("--output", "-o", default=None, help="输出目录 (默认: ./output)")
@click.option("--model", "-m", default=None, help="Claude 模型 (默认从配置读取)")
@click.option("--phase", "-p", default=None, type=click.Choice(["analyst", "architect", "backend", "test", "reviewer"]),
              help="只运行指定阶段")
def run(prd_file, name, output, model, phase):
    """从 PRD 文件运行完整流水线"""
    print_banner()

    # Read PRD
    prd_path = Path(prd_file)
    try:
        prd_text = prd_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        prd_text = prd_path.read_text(encoding="gbk")

    console.print(f"\n[bold]项目:[/] {name}")
    console.print(f"[bold]PRD 文件:[/] {prd_file} ({len(prd_text)} 字符)")
    console.print(f"[bold]模型:[/] {model or '默认'}\n")

    # Initialize context
    context = AgentContext(prd_raw=prd_text, project_name=name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]启动中...", total=6, completed=0)
        tracker = RichProgress(progress, task_id)

        pipeline = Pipeline(progress=tracker)

        if phase:
            # Single phase mode
            progress.update(task_id, description=f"[cyan]Single Phase[/] {phase}", total=2)
            context = pipeline.run_single_agent(phase, context)
            progress.update(task_id, completed=2)
        else:
            # Full pipeline
            context = pipeline.run(prd_text, name)

        progress.update(task_id, description="[bold green]完成![/]", completed=6)

    # Print summary
    print_context_summary(context)

    # Write outputs
    output_dir = Path(output) if output else OUTPUT_DIR
    writer = OutputWriter(output_dir)
    out_path = writer.write_all(context)

    console.print(f"\n[bold green][OK] 全部产物已输出到:[/] {out_path}")

    # List output files
    files = sorted(out_path.iterdir())
    console.print("\n[bold]输出文件:[/]")
    for f in files:
        icon = "[FILE]" if f.suffix in (".md", ".yaml", ".json") else "[DIR]"
        console.print(f"  {icon} {f.name}")

    # Show review warnings if any
    if context.review_report and context.review_report.consistency_issues:
        errors = [i for i in context.review_report.consistency_issues if i.severity == "error"]
        warnings = [i for i in context.review_report.consistency_issues if i.severity == "warning"]
        if errors:
            console.print(f"\n[yellow][WARN] 发现 {len(errors)} 个错误, {len(warnings)} 个警告[/]")
            console.print("  请查看审查报告了解详情。")


@main.command()
@click.argument("text", required=False)
def quick(text):
    """快速分析一段简短需求文本 (不经过完整流水线)"""
    if not text:
        text = click.get_text_stream("stdin").read()

    print_banner()
    console.print(f"\n[bold]需求文本:[/] {text[:200]}...")

    from src.agents.product_analyst import ProductAnalyst
    context = AgentContext(prd_raw=text, project_name="Quick Analysis")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        progress.add_task("[cyan]分析需求...", total=None)
        agent = ProductAnalyst()
        context = agent.run(context)

    console.print("\n[bold green][OK] 快速分析完成[/]\n")

    for s in context.user_stories:
        console.print(f"  [cyan]{s.id}[/]: {s.title} [dim]({s.priority.value})[/]")


@main.command()
def check():
    """检查配置和依赖是否就绪"""
    print_banner()

    from src.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

    checks = []

    # Check API key
    if ANTHROPIC_API_KEY:
        masked = ANTHROPIC_API_KEY[:8] + "..." + ANTHROPIC_API_KEY[-4:]
        checks.append(("API Key", True, f"已设置 ({masked})"))
    else:
        checks.append(("API Key", False, "未设置 — 请设置 ANTHROPIC_API_KEY"))

    # Check anthropic SDK
    try:
        import anthropic
        checks.append(("Anthropic SDK", True, f"v{anthropic.__version__}"))
    except ImportError:
        checks.append(("Anthropic SDK", False, "未安装 — pip install anthropic"))

    # Check pydantic
    try:
        import pydantic
        checks.append(("Pydantic", True, f"v{pydantic.__version__}"))
    except ImportError:
        checks.append(("Pydantic", False, "未安装 — pip install pydantic"))

    # Display
    table = Table(title="环境检查")
    table.add_column("组件")
    table.add_column("状态")
    table.add_column("详情")

    for name, ok, detail in checks:
        status = "[green][OK][/]" if ok else "[red][FAIL][/]"
        table.add_row(name, status, detail)

    console.print(table)
    console.print(f"\n[bold]默认模型:[/] {ANTHROPIC_MODEL}")


@main.command()
@click.option("--host", "-h", default="0.0.0.0", help="监听地址")
@click.option("--port", "-p", default=8000, help="监听端口")
@click.option("--reload/--no-reload", default=True, help="热重载")
def web(host, port, reload):
    """启动 Web 可视化界面"""
    import uvicorn
    print_banner()
    console.print(f"\n[bold green]Web 界面已启动[/]")
    console.print(f"  地址: [bold cyan]http://localhost:{port}[/]")
    console.print(f"  API 文档: [bold cyan]http://localhost:{port}/docs[/]")
    console.print("\n  按 Ctrl+C 停止服务器\n")
    uvicorn.run("src.web_server:app", host=host, port=port, reload=reload)


@main.command()
def desktop():
    """启动桌面客户端 (原生窗口)"""
    print_banner()
    console.print("\n[bold green]正在启动桌面客户端...[/]\n")
    from src.desktop_app import main as desktop_main
    desktop_main()


if __name__ == "__main__":
    main()
