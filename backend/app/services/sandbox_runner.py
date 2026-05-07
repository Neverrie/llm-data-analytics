from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass
class SandboxLimits:
    timeout_seconds: int = 30
    memory: str = "768m"
    cpus: str = "1"
    pids_limit: int = 128
    max_stdout_chars: int = 12000
    max_stderr_chars: int = 12000
    max_files: int = 20
    max_file_size: int = 5 * 1024 * 1024


@dataclass
class SandboxResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    files: list[dict[str, Any]] | None = None
    elapsed_seconds: float = 0.0
    reason: str | None = None


class SandboxRunner:
    def run(
        self,
        *,
        script_path: Path,
        work_dir: Path,
        dataset_path: Path | None,
        limits: SandboxLimits,
    ) -> SandboxResult:
        raise NotImplementedError


class LocalSubprocessRunner(SandboxRunner):
    def run(
        self,
        *,
        script_path: Path,
        work_dir: Path,
        dataset_path: Path | None,
        limits: SandboxLimits,
    ) -> SandboxResult:
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=limits.timeout_seconds,
                cwd=work_dir,
            )
            status = "success" if proc.returncode == 0 else "error"
            return SandboxResult(
                status=status,
                stdout=(proc.stdout or "")[: limits.max_stdout_chars],
                stderr=(proc.stderr or "")[: limits.max_stderr_chars],
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult(
                status="timeout",
                stdout=(exc.stdout or "")[: limits.max_stdout_chars],
                stderr=f"Execution timeout exceeded {limits.timeout_seconds} seconds.",
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )


class DockerSandboxRunner(SandboxRunner):
    def __init__(self, image: str) -> None:
        self.image = image
        self._preflight_checked = False
        self._preflight_error: str | None = None

    def _preflight_check(self) -> str | None:
        if self._preflight_checked:
            return self._preflight_error
        self._preflight_checked = True

        docker_bin = shutil.which("docker")
        if not docker_bin:
            self._preflight_error = (
                "Sandbox Docker runner is not available: docker CLI not found. "
                "Install docker CLI in backend container image."
            )
            return self._preflight_error

        sock = Path("/var/run/docker.sock")
        if not sock.exists():
            self._preflight_error = (
                "Sandbox Docker runner is not available: docker daemon socket unavailable "
                "(/var/run/docker.sock is not mounted)."
            )
            return self._preflight_error

        try:
            ver = subprocess.run(
                [docker_bin, "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if ver.returncode != 0:
                err = (ver.stderr or ver.stdout or "").strip()
                self._preflight_error = (
                    "Sandbox Docker runner is not available: cannot connect to docker daemon via socket. "
                    f"Details: {err[:220]}"
                )
                return self._preflight_error
        except Exception as exc:
            self._preflight_error = (
                "Sandbox Docker runner is not available: docker daemon check failed. "
                f"Details: {str(exc)[:220]}"
            )
            return self._preflight_error

        try:
            inspect = subprocess.run(
                [docker_bin, "image", "inspect", self.image],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if inspect.returncode != 0:
                self._preflight_error = (
                    f"Sandbox Docker runner is not available: sandbox image missing ({self.image}). "
                    "Build it with `docker compose build sandbox-runner-image` or `docker compose up -d --build`."
                )
                return self._preflight_error
        except Exception as exc:
            self._preflight_error = (
                "Sandbox Docker runner is not available: sandbox image check failed. "
                f"Details: {str(exc)[:220]}"
            )
            return self._preflight_error

        self._preflight_error = None
        return None

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except Exception:
            return False

    def map_container_path_to_host(self, path: Path) -> Path:
        resolved = path.resolve()
        outputs_root = Path(settings.outputs_dir).resolve()
        datasets_root = Path(settings.datasets_dir).resolve()

        host_outputs = (settings.host_outputs_dir or "").strip()
        host_datasets = (settings.host_datasets_dir or "").strip()

        if self._is_within(resolved, outputs_root):
            if not host_outputs:
                raise RuntimeError(
                    "Docker sandbox requires HOST_OUTPUTS_DIR because backend runs inside a container."
                )
            rel = resolved.relative_to(outputs_root)
            return (Path(host_outputs).resolve() / rel).resolve()

        if self._is_within(resolved, datasets_root):
            if not host_datasets:
                raise RuntimeError(
                    "Docker sandbox requires HOST_DATASETS_DIR because dataset is mounted from backend container path."
                )
            rel = resolved.relative_to(datasets_root)
            return (Path(host_datasets).resolve() / rel).resolve()

        return resolved

    @staticmethod
    def _is_windows_host_path(path_str: str) -> bool:
        return bool(WINDOWS_DRIVE_RE.match(path_str.strip()))

    @staticmethod
    def _join_host_path(base: str, rel: Path) -> str:
        base_clean = base.strip()
        rel_posix = rel.as_posix()
        if DockerSandboxRunner._is_windows_host_path(base_clean):
            base_norm = base_clean.replace("\\", "/").rstrip("/")
            return f"{base_norm}/{rel_posix}" if rel_posix else base_norm
        return str((Path(base_clean).resolve() / rel).resolve())

    def run(
        self,
        *,
        script_path: Path,
        work_dir: Path,
        dataset_path: Path | None,
        limits: SandboxLimits,
    ) -> SandboxResult:
        started = time.perf_counter()
        preflight_error = self._preflight_check()
        if preflight_error:
            return SandboxResult(status="error", stderr=preflight_error)

        docker_bin = shutil.which("docker")
        if not docker_bin:
            return SandboxResult(
                status="error",
                stderr="Sandbox Docker runner is not available: docker CLI not found.",
            )

        if not script_path.exists():
            return SandboxResult(
                status="error",
                stderr=f"Sandbox Docker runner is not available: script path not found before run: {script_path}",
            )

        host_outputs_env = (settings.host_outputs_dir or "").strip()
        host_datasets_env = (settings.host_datasets_dir or "").strip()
        if not host_outputs_env:
            return SandboxResult(
                status="error",
                stderr="Docker sandbox requires HOST_OUTPUTS_DIR because backend runs inside a container.",
            )
        if dataset_path and not host_datasets_env:
            return SandboxResult(
                status="error",
                stderr="Docker sandbox requires HOST_DATASETS_DIR because dataset is mounted from backend container path.",
            )
        work_rel = work_dir.resolve().relative_to(Path(settings.outputs_dir).resolve())
        host_work_dir_str = self._join_host_path(host_outputs_env, work_rel)
        host_dataset_path_str: str | None = None
        if dataset_path:
            ds_rel = dataset_path.resolve().relative_to(Path(settings.datasets_dir).resolve())
            host_dataset_path_str = self._join_host_path(host_datasets_env, ds_rel)
        host_work_dir_clean = host_work_dir_str.rstrip("/\\")
        host_script_path = f"{host_work_dir_clean}/{script_path.name}"

        logger.info(
            "SANDBOX_DOCKER_PATHS work_dir=%s host_work_dir=%s dataset_path=%s host_dataset_path=%s",
            str(work_dir),
            host_work_dir_str,
            str(dataset_path) if dataset_path else "-",
            host_dataset_path_str or "-",
        )
        is_win_paths = self._is_windows_host_path(host_work_dir_str)
        if not is_win_paths:
            host_work_dir_path = Path(host_work_dir_str)
            if not host_work_dir_path.exists():
                return SandboxResult(status="error", stderr=f"Host work dir does not exist: {host_work_dir_path}")
            if not (host_work_dir_path / "script.py").exists():
                return SandboxResult(
                    status="error",
                    stderr=f"Host script path not found before docker run: {host_work_dir_path / 'script.py'}",
                )
            if host_dataset_path_str and not self._is_windows_host_path(host_dataset_path_str):
                if not Path(host_dataset_path_str).exists():
                    return SandboxResult(
                        status="error",
                        stderr=f"Host dataset path not found before docker run: {host_dataset_path_str}",
                    )

        user_spec = str(getattr(settings, "sandbox_docker_user", "1000:1000")).strip() or "1000:1000"
        write_test_cmd = [
            docker_bin,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "MPLCONFIGDIR=/tmp/matplotlib",
            "--pids-limit",
            str(limits.pids_limit),
            "--memory",
            limits.memory,
            "--cpus",
            limits.cpus,
            "--user",
            user_spec,
            "-v",
            f"{host_work_dir_str}:/work:rw",
            "-w",
            "/work",
            self.image,
            "sh",
            "-lc",
            "test -f /work/script.py && touch /work/.write_test && rm /work/.write_test",
        ]
        logger.info(
            "SANDBOX_DOCKER_PREFLIGHT work_dir=%s user=%s script_exists_in_backend=%s expected_host_script=%s",
            "/work",
            user_spec,
            str(script_path.exists()),
            host_script_path,
        )
        preflight = subprocess.run(
            write_test_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if preflight.returncode != 0:
            err = (preflight.stderr or preflight.stdout or "").strip()
            return SandboxResult(
                status="error",
                stderr=(
                    f"Sandbox work directory is not writable by user {user_spec}. "
                    "Check HOST_OUTPUTS_DIR permissions or SANDBOX_DOCKER_USER. "
                    f"Details: {err[:400]}"
                ),
            )

        cmd = [
            docker_bin,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "MPLCONFIGDIR=/tmp/matplotlib",
            "--pids-limit",
            str(limits.pids_limit),
            "--memory",
            limits.memory,
            "--cpus",
            limits.cpus,
            "--user",
            user_spec,
            "-v",
            f"{host_work_dir_str}:/work:rw",
            "-w",
            "/work",
        ]
        if host_dataset_path_str:
            cmd.extend(["-v", f"{host_dataset_path_str}:/input/dataset.csv:ro"])
        cmd.extend([self.image, "python", "/work/script.py"])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=limits.timeout_seconds + 5,
            )
            if (
                proc.returncode != 0
                and user_spec != "0:0"
                and bool(getattr(settings, "sandbox_allow_root_retry", False))
                and ("PermissionError" in (proc.stderr or "") or "Errno 13" in (proc.stderr or ""))
            ):
                logger.warning(
                    "SANDBOX_DOCKER_RETRY_AS_ROOT is dev fallback and should not be used in production. reason=permission_denied user=%s",
                    user_spec,
                )
                retry_cmd = list(cmd)
                retry_user_idx = retry_cmd.index("--user") + 1
                retry_cmd[retry_user_idx] = "0:0"
                proc = subprocess.run(
                    retry_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=limits.timeout_seconds + 5,
                )
            status = "success" if proc.returncode == 0 else "error"
            return SandboxResult(
                status=status,
                stdout=(proc.stdout or "")[: limits.max_stdout_chars],
                stderr=(proc.stderr or "")[: limits.max_stderr_chars],
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult(
                status="timeout",
                stdout=(exc.stdout or "")[: limits.max_stdout_chars],
                stderr=f"Execution timeout exceeded {limits.timeout_seconds} seconds.",
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
        finally:
            try:
                created_files = [p.name for p in sorted(work_dir.iterdir()) if p.is_file()]
                logger.info("SANDBOX_DOCKER_WORKDIR_FILES work_dir=%s files=%s", str(work_dir), created_files[:50])
            except Exception:
                pass
