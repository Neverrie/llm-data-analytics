from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class AgentRunState:
    run_id: str
    cancelled: bool = False
    containers: set[str] = field(default_factory=set)


_lock = threading.Lock()
_runs: dict[str, AgentRunState] = {}


def create_run(run_id: str) -> AgentRunState:
    with _lock:
        state = AgentRunState(run_id=run_id)
        _runs[run_id] = state
        return state


def get_run(run_id: str) -> AgentRunState | None:
    with _lock:
        return _runs.get(run_id)


def cancel_run(run_id: str) -> bool:
    with _lock:
        state = _runs.get(run_id)
        if state is None:
            return False
        state.cancelled = True
        return True


def is_cancelled(run_id: str | None) -> bool:
    if not run_id:
        return False
    with _lock:
        state = _runs.get(run_id)
        return bool(state and state.cancelled)


def register_container(run_id: str | None, container_name: str) -> None:
    if not run_id:
        return
    with _lock:
        state = _runs.get(run_id)
        if state:
            state.containers.add(container_name)


def unregister_container(run_id: str | None, container_name: str) -> None:
    if not run_id:
        return
    with _lock:
        state = _runs.get(run_id)
        if state and container_name in state.containers:
            state.containers.remove(container_name)


def get_container_names(run_id: str) -> list[str]:
    with _lock:
        state = _runs.get(run_id)
        return sorted(state.containers) if state else []

