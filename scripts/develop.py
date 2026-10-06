"""Linux/WSL contributor commands; bootstrap uses only the Python standard library."""
from __future__ import annotations

import argparse
import base64
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PYTHON = BACKEND / ".venv/bin/python"
LOCAL = ROOT / ".local"


def run(args: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def require_node() -> None:
    if not shutil.which("node") or not shutil.which("npm"):
        raise RuntimeError("Install Node.js 20+ with npm before running setup.")
    major = int(subprocess.check_output(["node", "-p", "process.versions.node.split('.')[0]"], text=True))
    if major < 20:
        raise RuntimeError("Node.js 20+ is required; see .nvmrc.")


def ensure_env() -> None:
    LOCAL.mkdir(exist_ok=True, mode=0o700)
    env_path = ROOT / ".env"
    if not env_path.exists():
        template = (ROOT / ".env.example").read_text()
        template = template.replace("__JWT_SECRET__", secrets.token_urlsafe(48))
        template = template.replace("__FERNET_KEY__", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        # Absolute paths keep native data stable when commands run from backend/.
        template = template.replace("sqlite:///.local/optiq.db", f"sqlite:///{LOCAL / 'optiq.db'}")
        template = template.replace("MAIL_DIRECTORY=.local/mail", f"MAIL_DIRECTORY={LOCAL / 'mail'}")
        with env_path.open("x") as output:
            env_path.chmod(0o600)
            output.write(template)
        print("Created .env with fresh local secrets.", flush=True)
    else:
        print("Keeping existing .env and secrets.", flush=True)
    frontend_env = FRONTEND / ".env.local"
    if not frontend_env.exists():
        frontend_env.write_text("NEXT_PUBLIC_API_URL=http://localhost:8000\nNEXT_PUBLIC_MLFLOW_URL=\n")


def backend_env() -> dict[str, str]:
    return {**os.environ, "OPTIQ_ENV_FILE": str(ROOT / ".env")}


def require_setup() -> None:
    if not PYTHON.exists() or not (FRONTEND / "node_modules/next/package.json").exists() or not (ROOT / ".env").exists():
        raise RuntimeError("Run ./scripts/optiq setup first.")


def migrate() -> None:
    run([str(PYTHON), "-m", "alembic", "upgrade", "head"], BACKEND, backend_env())


def setup(extras: bool) -> None:
    require_node()
    if not PYTHON.exists():
        if shutil.which("uv"):
            run(["uv", "venv", "--python", sys.executable, str(BACKEND / ".venv")])
        else:
            run([sys.executable, "-m", "venv", str(BACKEND / ".venv")])
    requirements = [BACKEND / "requirements-dev.txt"]
    if extras:
        requirements.append(BACKEND / "requirements-extras.txt")
    install = ["uv", "pip", "install", "--python", str(PYTHON)] if shutil.which("uv") else [str(PYTHON), "-m", "pip", "install"]
    for requirement in requirements:
        install.extend(["-r", str(requirement)])
    run(install)
    run(["npm", "ci", "--no-audit", "--no-fund"], FRONTEND)
    ensure_env()
    migrate()
    print("Setup complete. Start with ./scripts/optiq dev", flush=True)


def check(build: bool) -> None:
    require_setup()
    # Checks never load contributor secrets or need a live database/provider.
    check_env = {
        **os.environ, "OPTIQ_ENV_FILE": "/dev/null", "DATABASE_URL": "sqlite://",
        "FRONTEND_URL": "http://localhost:3000",
        "DEBUG": "false", "JOB_BACKEND": "rq", "MAIL_BACKEND": "smtp", "MLFLOW_TRACKING_URI": "",
    }
    run([str(PYTHON), "-m", "ruff", "check", "."], BACKEND, check_env)
    run([str(PYTHON), "-m", "ruff", "check", str(ROOT / "scripts/develop.py")], BACKEND, check_env)
    run([str(PYTHON), "-m", "pytest", "-q"], BACKEND, check_env)
    run(["npm", "run", "lint"], FRONTEND)
    run(["npm", "exec", "tsc", "--", "--noEmit"], FRONTEND)
    if build:
        run(["npm", "run", "build"], FRONTEND)


def doctor() -> None:
    print(f"Python: {sys.version.split()[0]}", flush=True)
    require_node()
    print("Node/npm: available", flush=True)
    require_setup()
    code = '''from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine
with engine.connect() as connection:
    connection.execute(text("SELECT 1"))
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
print("Database:", engine.dialect.name, "migration:", revision)
print("Jobs:", settings.job_backend, "mail:", settings.mail_backend)
if settings.job_backend == "rq":
    from app.workers.queue import experiment_queue
    experiment_queue().connection.ping()
    print("Redis: reachable (start an RQ worker separately)")
if settings.mail_backend == "file":
    print("Local mail directory:", settings.mail_directory)
print("MLflow:", "enabled" if settings.mlflow_tracking_uri else "disabled")
'''
    run([str(PYTHON), "-c", code], ROOT, backend_env() | {"PYTHONPATH": str(BACKEND)})
    print("Native development does not require Docker. For Compose, check docker info and docker compose version.")


def free_port(port: int) -> None:
    try:
        with socket.socket() as sock:
            # Match the servers' restart behavior when old connections are in TIME_WAIT.
            # This still rejects ports with an active listener.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
    except OSError as exc:
        raise RuntimeError(f"Cannot bind port {port}: {exc}. Choose --api-port / --web-port if occupied.") from exc


def stop(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def dev(api_port: int, web_port: int) -> None:
    require_setup()
    if api_port == web_port:
        raise RuntimeError("API and frontend ports must differ.")
    free_port(api_port)
    free_port(web_port)
    migrate()
    processes = []
    api_env = backend_env() | {"FRONTEND_URL": f"http://localhost:{web_port}"}
    web_env = os.environ | {"NEXT_PUBLIC_API_URL": f"http://localhost:{api_port}", "NEXT_TELEMETRY_DISABLED": "1"}
    try:
        processes.append(subprocess.Popen(
            [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port), "--reload"],
            cwd=BACKEND, env=api_env, start_new_session=True,
        ))
        deadline = time.monotonic() + 30
        while True:
            if processes[0].poll() is not None:
                raise RuntimeError("API exited during startup; see its output above.")
            try:
                with urlopen(f"http://127.0.0.1:{api_port}/health", timeout=1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("API did not become ready in 30 seconds.")
                time.sleep(0.25)
        processes.append(subprocess.Popen(
            ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(web_port)],
            cwd=FRONTEND, env=web_env, start_new_session=True,
        ))
        print(f"App: http://localhost:{web_port} | API docs: http://localhost:{api_port}/docs", flush=True)
        print("Verification emails: .local/mail/*.eml. Ctrl+C stops both servers.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        raise RuntimeError("A development server exited; stopping the other server.")
    except KeyboardInterrupt:
        print("\nStopping development servers.")
    finally:
        for process in reversed(processes):
            stop(process)


def compose(args: list[str]) -> None:
    if not shutil.which("docker"):
        raise RuntimeError("Install Docker Engine and the Compose plugin. Docker Desktop is optional.")
    run(["docker", "info"], env=os.environ.copy())
    run(["docker", "compose", "version"])
    ensure_env()
    run(["docker", "compose", "--project-directory", str(ROOT), "--env-file", str(ROOT / ".env"),
         "-f", str(ROOT / "infra/docker-compose.yml"), *args])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup").add_argument("--extras", action="store_true", help="Also install MLflow and Ragas")
    start = commands.add_parser("dev")
    start.add_argument("--api-port", type=int, default=8000)
    start.add_argument("--web-port", type=int, default=3000)
    commands.add_parser("doctor")
    commands.add_parser("check").add_argument("--build", action="store_true")
    commands.add_parser("compose", add_help=False).add_argument("args", nargs=argparse.REMAINDER)
    # Forward Compose flags without interpreting them as our own flags.
    if len(sys.argv) > 1 and sys.argv[1] == "compose":
        compose(sys.argv[2:])
        return
    args = parser.parse_args()
    if args.command == "setup":
        setup(args.extras)
    elif args.command == "dev":
        dev(args.api_port, args.web_port)
    elif args.command == "check":
        check(args.build)
    elif args.command == "doctor":
        doctor()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
