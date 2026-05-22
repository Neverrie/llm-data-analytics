from app.sandbox.docker_runner import DockerSandboxRunner
from app.sandbox.runner import SandboxRunner


def get_sandbox_runner() -> SandboxRunner:
    return DockerSandboxRunner()
