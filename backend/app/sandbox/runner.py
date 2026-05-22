from typing import Protocol

from app.sandbox.models import SandboxResult, SandboxRunRequest


class SandboxRunner(Protocol):
    def run(self, request: SandboxRunRequest) -> SandboxResult:
        ...
