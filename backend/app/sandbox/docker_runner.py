import mimetypes
import re
import subprocess
import time
from pathlib import Path

from app.config import settings
from app.sandbox.models import SandboxFile, SandboxResult, SandboxRunRequest


_MIME_OVERRIDES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
}


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _is_windows_path(raw: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", raw))


def _strip_trailing_slashes(raw: str) -> str:
    return raw.rstrip("/\\")


def _windows_to_docker_host_mount(raw: str) -> str:
    normalized = raw.replace("\\", "/")
    match = re.match(r"^([A-Za-z]):/(.*)$", normalized)
    if not match:
        return normalized
    drive = match.group(1).lower()
    tail = match.group(2)
    return f"/run/desktop/mnt/host/{drive}/{tail}"


def _to_docker_mount_source(path_raw: str) -> str:
    if _is_windows_path(path_raw):
        return _windows_to_docker_host_mount(path_raw)
    return path_raw


def _map_container_to_host_path(path: Path) -> str:
    raw = str(path)
    if _is_windows_path(raw):
        return raw

    outputs = str(settings.outputs_dir or "").strip()
    host_outputs = str(settings.host_outputs_dir or "").strip()
    datasets = str(settings.datasets_dir or "").strip()
    host_datasets = str(settings.host_datasets_dir or "").strip()

    if outputs and host_outputs and raw.startswith(_strip_trailing_slashes(outputs) + "/"):
        suffix = raw[len(_strip_trailing_slashes(outputs)) :].lstrip("/")
        return f"{_strip_trailing_slashes(host_outputs)}/{suffix}".replace("\\", "/")

    if datasets and host_datasets and raw.startswith(_strip_trailing_slashes(datasets) + "/"):
        suffix = raw[len(_strip_trailing_slashes(datasets)) :].lstrip("/")
        return f"{_strip_trailing_slashes(host_datasets)}/{suffix}".replace("\\", "/")

    return str(path.resolve())


def _is_hidden_or_temp(path: Path, work_dir: Path) -> bool:
    rel_parts = path.relative_to(work_dir).parts
    if not rel_parts:
        return True
    if any(part.startswith(".") for part in rel_parts):
        return True
    if any(part == "__pycache__" for part in rel_parts):
        return True
    name = path.name
    if name == "script.py":
        return True
    if name.startswith("~"):
        return True
    return False


def _collect_files(work_dir: Path) -> list[SandboxFile]:
    files: list[SandboxFile] = []
    for item in work_dir.rglob("*"):
        if not item.is_file():
            continue
        if _is_hidden_or_temp(item, work_dir):
            continue
        ext = item.suffix.lower()
        mime = _MIME_OVERRIDES.get(ext)
        if not mime:
            guessed, _ = mimetypes.guess_type(item.name)
            mime = guessed
        files.append(
            SandboxFile(
                path=str(item),
                filename=item.name,
                size_bytes=item.stat().st_size,
                mime_type=mime,
            )
        )
    return files


def _ensure_host_dir(path_like: str) -> str:
    host_path = _map_container_to_host_path(Path(path_like))
    Path(host_path).mkdir(parents=True, exist_ok=True)
    return host_path


class DockerSandboxRunner:
    def _run_once(self, cmd: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )

    def run(self, request: SandboxRunRequest) -> SandboxResult:
        work_dir = request.work_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        script_path = work_dir / "script.py"
        script_path.write_text(request.code, encoding="utf-8")

        host_work_dir = _map_container_to_host_path(work_dir)
        docker_work_dir = _to_docker_mount_source(host_work_dir)

        base_cmd: list[str] = [
            "docker",
            "run",
            "--rm",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            str(request.limits.memory),
            "--cpus",
            str(request.limits.cpus),
            "--pids-limit",
            str(request.limits.pids_limit),
            "-v",
            f"{docker_work_dir}:/work:rw",
        ]
        if settings.sandbox_allow_network:
            base_cmd.extend(["--network", "bridge"])
        else:
            base_cmd.extend(["--network", "none"])

        host_userbase = _ensure_host_dir(str(settings.sandbox_python_userbase_dir))
        docker_userbase = _to_docker_mount_source(host_userbase)
        host_pip_cache = _ensure_host_dir(str(settings.sandbox_pip_cache_dir))
        docker_pip_cache = _to_docker_mount_source(host_pip_cache)
        base_cmd.extend(
            [
                "-v",
                f"{docker_userbase}:/opt/userbase:rw",
                "-v",
                f"{docker_pip_cache}:/opt/pip-cache:rw",
            ]
        )

        if request.dataset_path is not None:
            host_dataset = _map_container_to_host_path(request.dataset_path)
            docker_dataset = _to_docker_mount_source(host_dataset)
            base_cmd.extend(["-v", f"{docker_dataset}:/input/dataset.csv:ro"])

        base_cmd.extend(
            [
                "-e",
                "MPLCONFIGDIR=/tmp/matplotlib",
                "-e",
                "PYTHONUNBUFFERED=1",
                "-e",
                "PYTHONUSERBASE=/opt/userbase",
                "-e",
                "PIP_CACHE_DIR=/opt/pip-cache",
                "-e",
                "PYTHONPATH=/opt/userbase/lib/python3.12/site-packages",
            ]
        )

        user_value = str(settings.sandbox_docker_user)
        run_cmd = [*base_cmd, "--user", user_value, str(settings.sandbox_docker_image), "python", "/work/script.py"]

        start = time.perf_counter()
        try:
            proc = self._run_once(run_cmd, request.limits.timeout_seconds)

            elapsed = time.perf_counter() - start
            status = "success" if proc.returncode == 0 else "error"
            return SandboxResult(
                status=status,
                stdout=_truncate(proc.stdout or "", request.limits.max_output_chars),
                stderr=_truncate(proc.stderr or "", request.limits.max_output_chars),
                files=_collect_files(work_dir),
                elapsed_seconds=elapsed,
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - start
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
            return SandboxResult(
                status="timeout",
                stdout=_truncate(stdout, request.limits.max_output_chars),
                stderr=_truncate(stderr, request.limits.max_output_chars),
                files=_collect_files(work_dir),
                elapsed_seconds=elapsed,
                exit_code=None,
            )
