from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .ai_action_registry_step09 import (
    AIExecutionRecord,
    PlanPreview,
    Step09ActionError,
    Step09TransactionEngine,
)
from .ai_agent_core_step09 import (
    AgentContextSnapshot,
    AgentPlan,
    AgentState,
    AgentStateMachine,
    PermissionGrant,
    ProviderInterpretation,
)
from .ai_history_step09 import AgentHistoryStore
from .editor_controller import EditorController


@dataclass(frozen=True)
class AgentSessionSnapshot:
    state: AgentState
    prompt: str
    message: str
    clarification: str
    plan: AgentPlan | None
    preview: PlanPreview | None
    execution: AIExecutionRecord | None
    error: str


class AgentSessionService:
    """Stateful orchestration with one mutation boundary: Step09TransactionEngine."""

    def __init__(
        self,
        controller: EditorController,
        *,
        grant: PermissionGrant | None = None,
        history_store: AgentHistoryStore | None = None,
    ) -> None:
        self.controller = controller
        self.transaction = Step09TransactionEngine(controller)
        self.grant = grant or PermissionGrant.all_editor_writes()
        self.history_store = history_store
        self.machine = AgentStateMachine()
        self.prompt = ""
        self.message = ""
        self.clarification = ""
        self.context: AgentContextSnapshot | None = None
        self.plan: AgentPlan | None = None
        self.preview_result: PlanPreview | None = None
        self.execution: AIExecutionRecord | None = None

    def snapshot(self) -> AgentSessionSnapshot:
        return AgentSessionSnapshot(
            state=self.machine.state,
            prompt=self.prompt,
            message=self.message,
            clarification=self.clarification,
            plan=self.plan,
            preview=self.preview_result,
            execution=self.execution,
            error=self.machine.error,
        )

    def _entry(
        self,
        role: str,
        text: str,
        *,
        status: str = "",
        plan: AgentPlan | None = None,
    ) -> None:
        if self.history_store is None:
            return
        try:
            self.history_store.append(
                entry_id=str(uuid4()),
                role=role,
                text=text,
                status=status or self.machine.state.value,
                plan_id=plan.plan_id if plan is not None else "",
                action_names=(action.name for action in plan.actions) if plan is not None else (),
            )
        except OSError:
            # History is optional product state; a persistence failure must never
            # change project state or turn a validated command transaction into a
            # false failure.
            pass

    def _clear_plan_state(self) -> None:
        self.message = ""
        self.clarification = ""
        self.plan = None
        self.preview_result = None
        self.execution = None

    def begin_interpretation(
        self,
        prompt: str,
        context: AgentContextSnapshot,
    ) -> AgentSessionSnapshot:
        prompt = " ".join(str(prompt).split())
        if not prompt:
            raise ValueError("Perintah AI tidak boleh kosong.")
        context.validate()
        if self.machine.state in {AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED}:
            self.machine.transition(AgentState.IDLE)
        if self.machine.state in {
            AgentState.NEEDS_CLARIFICATION,
            AgentState.PLAN_READY,
            AgentState.PREVIEW_READY,
        }:
            self.machine.transition(AgentState.INTERPRETING)
        elif self.machine.state == AgentState.IDLE:
            self.machine.transition(AgentState.INTERPRETING)
        elif self.machine.state != AgentState.INTERPRETING:
            raise ValueError("AI Agent sedang mengeksekusi dan belum dapat menerima perintah baru.")
        self.prompt = prompt
        self.context = context
        self._clear_plan_state()
        self._entry("user", prompt, status=AgentState.INTERPRETING.value)
        return self.snapshot()

    def receive_interpretation(
        self,
        result: ProviderInterpretation,
    ) -> AgentSessionSnapshot:
        if self.machine.state != AgentState.INTERPRETING:
            raise ValueError("Response provider datang di state yang sudah tidak relevan.")
        if not isinstance(result, ProviderInterpretation):
            raise TypeError("Provider result tidak valid.")
        self.message = str(result.message)
        if result.needs_clarification:
            self.clarification = str(result.clarification or result.message)
            self.machine.transition(AgentState.NEEDS_CLARIFICATION)
            self._entry("assistant", self.clarification, status=self.machine.state.value)
            return self.snapshot()

        assert result.plan is not None
        result.plan.validate()
        if self.context is None:
            raise ValueError("Context AI hilang sebelum plan diterima.")
        if result.plan.project_id != self.context.project_id:
            return self.fail("Plan provider berasal dari project_id berbeda.")
        if result.plan.expected_revision != self.context.revision:
            return self.fail("Plan provider memakai revision yang berbeda dari context.")
        if result.plan.context_fingerprint != self.context.fingerprint:
            return self.fail("Plan provider memakai context fingerprint yang berbeda.")
        self.plan = result.plan
        self.machine.transition(AgentState.PLAN_READY)
        self._entry("assistant", self.message or "Rencana siap.", status=self.machine.state.value, plan=self.plan)
        return self.snapshot()

    def preview(self) -> AgentSessionSnapshot:
        if self.machine.state != AgentState.PLAN_READY or self.plan is None or self.context is None:
            raise ValueError("Preview Diff hanya tersedia setelah AgentPlan siap.")
        try:
            self.preview_result = self.transaction.dry_run(
                self.plan,
                self.context,
                self.grant,
            )
            self.machine.transition(AgentState.PREVIEW_READY)
            self._entry(
                "system",
                f"Preview Diff siap: {self.preview_result.command_count} domain command, impact {self.preview_result.impact.change_count}.",
                status=self.machine.state.value,
                plan=self.plan,
            )
            return self.snapshot()
        except Exception as exc:
            return self.fail(str(exc))

    def execute(self) -> AgentSessionSnapshot:
        if self.machine.state != AgentState.PREVIEW_READY or self.plan is None or self.context is None:
            raise ValueError("Jalankan hanya tersedia setelah Preview Diff siap.")
        self.machine.transition(AgentState.EXECUTING)
        try:
            self.execution = self.transaction.execute(
                self.plan,
                self.context,
                self.grant,
            )
            self.machine.transition(AgentState.COMPLETED)
            self.message = (
                "Selesai. Semua action plan dikomit sebagai satu transaction Undo."
                if not self.execution.duplicate
                else "Plan ini sudah pernah dijalankan; tidak ada mutation kedua."
            )
            self._entry("assistant", self.message, status=self.machine.state.value, plan=self.plan)
            return self.snapshot()
        except Exception as exc:
            return self.fail(str(exc))

    def cancel(self) -> AgentSessionSnapshot:
        if self.machine.state in {AgentState.IDLE, AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED}:
            return self.snapshot()
        if self.machine.state == AgentState.EXECUTING:
            # Execution commit is synchronous and atomic. There is no partial
            # transaction to interrupt safely once dispatch begins.
            raise Step09ActionError("Transaction sedang commit atomically dan tidak dapat dipotong di tengah.")
        self.machine.transition(AgentState.CANCELLED)
        self._entry("system", "Flow AI dibatalkan sebelum commit project.", status=self.machine.state.value)
        return self.snapshot()

    def fail(self, error: str) -> AgentSessionSnapshot:
        text = str(error or "AI Agent gagal tanpa detail.")
        if self.machine.state not in {
            AgentState.INTERPRETING,
            AgentState.PLAN_READY,
            AgentState.PREVIEW_READY,
            AgentState.EXECUTING,
        }:
            self.machine.reset()
            self.machine.transition(AgentState.INTERPRETING)
        self.machine.transition(AgentState.FAILED, error=text)
        self.message = text
        self._entry("system", text, status=self.machine.state.value, plan=self.plan)
        return self.snapshot()

    def undo_ai(self):
        restored = self.transaction.undo_ai()
        self._entry(
            "system",
            "Undo AI berhasil memulihkan project sebelum transaction AI terakhir.",
            status="UNDO_AI",
            plan=self.plan,
        )
        return restored

    @property
    def can_undo_ai(self) -> bool:
        return self.transaction.can_undo_ai()
