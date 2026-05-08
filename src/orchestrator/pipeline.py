"""Pipeline orchestrator for the Requirements-to-Code multi-agent system.

Pipeline:
  Phase 1: Product Analyst (sequential)
  Phase 2: Architect (sequential, depends on Phase 1)
  Phase 3a: Backend Developer  ─┐
  Phase 3b: Test Engineer      ─┤ (parallel)
  Phase 4: Reviewer            ─┘ (depends on 3a + 3b)
"""

import asyncio
import time
from typing import Optional, Callable

from src.models.artifacts import AgentContext
from src.agents.product_analyst import ProductAnalyst
from src.agents.architect import Architect
from src.agents.backend_dev import BackendDeveloper
from src.agents.test_engineer import TestEngineer
from src.agents.reviewer import Reviewer


class PipelineProgress:
    """Callback interface for pipeline progress updates."""

    def on_phase_start(self, phase: str, agent_name: str) -> None:
        pass

    def on_phase_end(self, phase: str, agent_name: str, duration_ms: float) -> None:
        pass

    def on_error(self, phase: str, error: str) -> None:
        pass


class Pipeline:
    """Orchestrates the multi-agent pipeline."""

    def __init__(self, progress: Optional[PipelineProgress] = None):
        self.progress = progress or PipelineProgress()

    def run(self, prd_text: str, project_name: str = "Unnamed Project") -> AgentContext:
        """Run the full pipeline synchronously. Returns the populated AgentContext."""
        return asyncio.run(self.run_async(prd_text, project_name))

    async def run_async(self, prd_text: str, project_name: str = "Unnamed Project") -> AgentContext:
        """Run the full pipeline asynchronously."""
        context = AgentContext(prd_raw=prd_text, project_name=project_name)

        # ── Phase 1: Product Analyst ──────────────────────────────────
        context = await self._run_phase(
            "Phase 1/4", "Product Analyst", ProductAnalyst(), context
        )

        # ── Phase 2: Architect ────────────────────────────────────────
        context = await self._run_phase(
            "Phase 2/4", "Architect", Architect(), context
        )

        # ── Phase 3: Backend Dev + Test Engineer (parallel) ───────────
        self.progress.on_phase_start("Phase 3/4", "Backend Developer + Test Engineer")
        t_start = time.time()

        backend_agent = BackendDeveloper()
        test_agent = TestEngineer()

        # Run both in parallel — each returns an updated context
        # We pass a copy of context to each to avoid race conditions
        backend_task = asyncio.to_thread(backend_agent.run, context.model_copy(deep=True))
        test_task = asyncio.to_thread(test_agent.run, context.model_copy(deep=True))

        backend_ctx, test_ctx = await asyncio.gather(backend_task, test_task)

        # Merge results: Backend Dev owns code_artifacts, Test Engineer owns test_cases
        context.code_artifacts = backend_ctx.code_artifacts
        context.test_cases = test_ctx.test_cases

        elapsed = (time.time() - t_start) * 1000
        self.progress.on_phase_end("Phase 3/4", "Backend Developer + Test Engineer", elapsed)

        # ── Phase 4: Reviewer ─────────────────────────────────────────
        context = await self._run_phase(
            "Phase 4/4", "Reviewer", Reviewer(), context
        )

        return context

    async def _run_phase(
        self,
        phase_label: str,
        agent_name: str,
        agent,
        context: AgentContext,
    ) -> AgentContext:
        """Run a single agent phase and return updated context."""
        self.progress.on_phase_start(phase_label, agent_name)
        t_start = time.time()

        try:
            result = await asyncio.to_thread(agent.run, context)
            elapsed = (time.time() - t_start) * 1000
            self.progress.on_phase_end(phase_label, agent_name, elapsed)
            return result
        except Exception as e:
            self.progress.on_error(phase_label, str(e))
            raise

    def run_single_agent(self, agent_name: str, context: AgentContext) -> AgentContext:
        """Run a single agent by name. Useful for re-running one phase."""
        agents = {
            "analyst": ProductAnalyst,
            "architect": Architect,
            "backend": BackendDeveloper,
            "test": TestEngineer,
            "reviewer": Reviewer,
        }
        agent_cls = agents.get(agent_name)
        if not agent_cls:
            raise ValueError(f"Unknown agent: {agent_name}. Options: {list(agents.keys())}")
        return agent_cls().run(context)
