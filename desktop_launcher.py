"""
AfriSync Desktop Launcher v1

A Windows-friendly control panel for starting/stopping AfriSync services:
- Remote Server: http://127.0.0.1:8000
- Device A:      http://127.0.0.1:8001
- Device B:      http://127.0.0.1:8002
- Admin:         http://127.0.0.1:8010/admin

This launcher is intentionally separate from the main AfriSync application code.
It does not modify your databases or source files.
"""

from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Dict, List, Optional

APP_TITLE = "AfriSync Desktop Launcher"
VERSION = "v1.0"
HOST = "127.0.0.1"


@dataclass
class ServiceConfig:
    key: str
    label: str
    module: str
    port: int
    url: str
    env: Dict[str, str] = field(default_factory=dict)


class AfriSyncLauncher:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_TITLE} {VERSION}")
        self.root.geometry("1080x720")
        self.root.minsize(980, 640)

        self.project_root = self.resolve_project_root()
        self.processes: Dict[str, subprocess.Popen] = {}
        self.log_threads: Dict[str, threading.Thread] = {}
        self.status_vars: Dict[str, tk.StringVar] = {}
        self.port_vars: Dict[str, tk.StringVar] = {}
        self.buttons: Dict[str, Dict[str, ttk.Button]] = {}
        self._closing = False

        self.services = self.build_services()
        self.configure_style()
        self.build_ui()
        self.refresh_status_loop()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def resolve_project_root(self) -> Path:
        env_root = os.environ.get("AFRISYNC_PROJECT_ROOT")
        if env_root:
            return Path(env_root).expanduser().resolve()

        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent

        return Path(__file__).resolve().parent

    def configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("SubTitle.TLabel", font=("Segoe UI", 10))
        style.configure("Service.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))

    def build_services(self) -> List[ServiceConfig]:
        base_remote_url = os.environ.get("AFRISYNC_REMOTE_URL", f"http://{HOST}:8000")
        return [
            ServiceConfig(
                key="remote",
                label="Remote Server",
                module="server:app",
                port=8000,
                url=f"http://{HOST}:8000/health",
                env={
                    "AFRISYNC_SERVER_DB": "server.db",
                    "AFRISYNC_SERVER_UPLOAD_ROOT": "server_uploads",
                    "AFRISYNC_SYNC_SECRET_FILE": ".afrisync_server_secret",
                    "AFRISYNC_SMTP_HOST": "smtp.gmail.com",
                    "AFRISYNC_SMTP_PORT": "587",
                    "AFRISYNC_SMTP_USE_SSL": "0",
                    "AFRISYNC_SMTP_FROM_NAME": "AfriSync",
                    "AFRISYNC_EMAIL_REQUIRE_SMTP": "1",
                    "AFRISYNC_EMAIL_ALLOW_DEVELOPMENT_CODE": "0",
                },
            ),
            ServiceConfig(
                key="device_a",
                label="Device A",
                module="local_app:app",
                port=8001,
                url=f"http://{HOST}:8001",
                env={
                    "AFRISYNC_DEVICE_NAME": "Device A",
                    "AFRISYNC_LOCAL_DB": "afrisync_device_a.db",
                    "AFRISYNC_UPLOAD_ROOT": "uploads_device_a",
                    "AFRISYNC_SESSION_COOKIE": "afrisync_device_a_session",
                    "AFRISYNC_REMOTE_URL": base_remote_url,
                },
            ),
            ServiceConfig(
                key="device_b",
                label="Device B",
                module="local_app:app",
                port=8002,
                url=f"http://{HOST}:8002",
                env={
                    "AFRISYNC_DEVICE_NAME": "Device B",
                    "AFRISYNC_LOCAL_DB": "afrisync_device_b.db",
                    "AFRISYNC_UPLOAD_ROOT": "uploads_device_b",
                    "AFRISYNC_SESSION_COOKIE": "afrisync_device_b_session",
                    "AFRISYNC_REMOTE_URL": base_remote_url,
                },
            ),
            ServiceConfig(
                key="admin",
                label="Admin Dashboard",
                module="admin_app:app",
                port=8010,
                url=f"http://{HOST}:8010/admin",
                env={
                    "AFRISYNC_SERVER_DB": "server.db",
                    "AFRISYNC_SERVER_UPLOAD_ROOT": "server_uploads",
                    "AFRISYNC_ADMIN_USERNAME": "admin",
                    "AFRISYNC_ADMIN_PASSWORD": os.environ.get("AFRISYNC_ADMIN_PASSWORD", "admin12345"),
                    "AFRISYNC_ADMIN_SESSION_HOURS": "8",
                },
            ),
        ]

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(header, text="AfriSync Desktop Launcher", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Start and manage Remote Server, Device A, Device B, and Admin Dashboard from one screen.",
            style="SubTitle.TLabel",
        ).pack(anchor=tk.W, pady=(2, 0))

        root_frame = ttk.Frame(outer)
        root_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(root_frame, text="Project folder:").pack(side=tk.LEFT)
        self.project_root_var = tk.StringVar(value=str(self.project_root))
        ttk.Entry(root_frame, textvariable=self.project_root_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(root_frame, text="Open Folder", command=self.open_project_folder).pack(side=tk.LEFT)

        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(actions, text="Start All", command=self.start_all).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Stop All", command=self.stop_all).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Open Device A", command=lambda: self.open_url(f"http://{HOST}:8001")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Open Device B", command=lambda: self.open_url(f"http://{HOST}:8002")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Open Admin", command=lambda: self.open_url(f"http://{HOST}:8010/admin")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Health Check", command=self.show_health_report).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Clear Logs", command=self.clear_logs).pack(side=tk.RIGHT)

        services_frame = ttk.Frame(outer)
        services_frame.pack(fill=tk.X, pady=(0, 12))

        for index, service in enumerate(self.services):
            frame = ttk.LabelFrame(services_frame, text=service.label, padding=10, style="Service.TLabelframe")
            frame.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 8, 0))
            services_frame.columnconfigure(index, weight=1)

            status_var = tk.StringVar(value="Stopped")
            port_var = tk.StringVar(value=f"Port {service.port}")
            self.status_vars[service.key] = status_var
            self.port_vars[service.key] = port_var

            ttk.Label(frame, textvariable=status_var, style="Status.TLabel").pack(anchor=tk.W)
            ttk.Label(frame, textvariable=port_var).pack(anchor=tk.W, pady=(2, 8))

            button_row = ttk.Frame(frame)
            button_row.pack(fill=tk.X)
            start_button = ttk.Button(button_row, text="Start", command=lambda s=service: self.start_service(s))
            stop_button = ttk.Button(button_row, text="Stop", command=lambda s=service: self.stop_service(s.key))
            open_button = ttk.Button(button_row, text="Open", command=lambda s=service: self.open_url(s.url))
            start_button.pack(side=tk.LEFT, padx=(0, 6))
            stop_button.pack(side=tk.LEFT, padx=(0, 6))
            open_button.pack(side=tk.LEFT)
            self.buttons[service.key] = {"start": start_button, "stop": stop_button, "open": open_button}

        log_frame = ttk.LabelFrame(outer, text="Service Logs", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=18, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log("Launcher ready.")
        self.log(f"Project root: {self.project_root}")
        self.log("Use Start All, then open Device A at http://127.0.0.1:8001")

    def build_env(self, service: ServiceConfig) -> Dict[str, str]:
        env = os.environ.copy()
        env.update(service.env)
        env.update(self.load_ps1_env("afrisync_email_config.ps1"))
        env.update(self.load_ps1_env("afrisync_google_config.ps1"))
        env.update(self.load_ps1_env("afrisync_production_config.ps1"))
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def load_ps1_env(self, filename: str) -> Dict[str, str]:
        path = self.project_root / filename
        if not path.exists():
            return {}
        values: Dict[str, str] = {}
        pattern = re.compile(r'^\s*\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\'](.*?)["\']\s*$')
        try:
            for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = pattern.match(raw_line.strip())
                if match:
                    values[match.group(1)] = match.group(2)
        except OSError as exc:
            self.log(f"Could not read {filename}: {exc}")
        return values

    def start_all(self) -> None:
        for service in self.services:
            self.start_service(service)
            time.sleep(0.5)
        self.root.after(2500, lambda: self.open_url(f"http://{HOST}:8001"))

    def stop_all(self) -> None:
        for key in list(self.processes.keys()):
            self.stop_service(key)

    def start_service(self, service: ServiceConfig) -> None:
        if service.key in self.processes and self.processes[service.key].poll() is None:
            self.log(f"{service.label} is already running.")
            return

        if not self.project_root.exists():
            messagebox.showerror("Project folder missing", f"Folder not found:\n{self.project_root}")
            return

        python_exe = sys.executable if not getattr(sys, "frozen", False) else self.find_python_executable()
        if not python_exe:
            messagebox.showerror("Python not found", "Python could not be found. Run this launcher from your AfriSync virtual environment or install Python.")
            return

        command = [python_exe, "-m", "uvicorn", service.module, "--host", HOST, "--port", str(service.port)]
        env = self.build_env(service)

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            messagebox.showerror("Python not found", f"Could not start Python executable:\n{python_exe}")
            return
        except Exception as exc:
            messagebox.showerror("Start failed", f"Could not start {service.label}:\n{exc}")
            return

        self.processes[service.key] = process
        self.log(f"Started {service.label} on port {service.port}.")

        thread = threading.Thread(target=self.capture_logs, args=(service, process), daemon=True)
        self.log_threads[service.key] = thread
        thread.start()
        self.refresh_status()

    def find_python_executable(self) -> Optional[str]:
        candidates = [
            self.project_root / ".venv" / "Scripts" / "python.exe",
            self.project_root / "venv" / "Scripts" / "python.exe",
            Path(sys.executable),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return "python"

    def stop_service(self, key: str) -> None:
        process = self.processes.get(key)
        service = self.get_service(key)
        label = service.label if service else key
        if not process or process.poll() is not None:
            self.log(f"{label} is not running.")
            self.processes.pop(key, None)
            self.refresh_status()
            return

        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
                time.sleep(0.8)
                if process.poll() is None:
                    process.terminate()
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            self.log(f"Stopped {label}.")
        except Exception as exc:
            self.log(f"Could not stop {label}: {exc}")
        finally:
            self.processes.pop(key, None)
            self.refresh_status()

    def capture_logs(self, service: ServiceConfig, process: subprocess.Popen) -> None:
        if not process.stdout:
            return
        try:
            for line in process.stdout:
                if self._closing:
                    break
                self.log(f"[{service.label}] {line.rstrip()}")
        except Exception as exc:
            self.log(f"[{service.label}] log capture stopped: {exc}")

    def get_service(self, key: str) -> Optional[ServiceConfig]:
        return next((service for service in self.services if service.key == key), None)

    def refresh_status_loop(self) -> None:
        self.refresh_status()
        if not self._closing:
            self.root.after(2000, self.refresh_status_loop)

    def refresh_status(self) -> None:
        for service in self.services:
            process = self.processes.get(service.key)
            process_running = bool(process and process.poll() is None)
            port_open = self.is_port_open(service.port)

            if process_running or port_open:
                if port_open:
                    status = "Running"
                else:
                    status = "Starting..."
            else:
                status = "Stopped"
                if process and process.poll() is not None:
                    self.processes.pop(service.key, None)

            self.status_vars[service.key].set(status)
            self.port_vars[service.key].set(f"Port {service.port}: {'open' if port_open else 'closed'}")

            buttons = self.buttons.get(service.key, {})
            if buttons:
                buttons["start"].configure(state=tk.DISABLED if process_running else tk.NORMAL)
                buttons["stop"].configure(state=tk.NORMAL if (process_running or port_open) else tk.DISABLED)

    def is_port_open(self, port: int) -> bool:
        try:
            with socket.create_connection((HOST, port), timeout=0.25):
                return True
        except OSError:
            return False

    def fetch_url(self, url: str, timeout: float = 2.0) -> str:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                body = response.read(500).decode("utf-8", errors="replace")
                return f"OK {response.status}: {body[:200]}"
        except urllib.error.HTTPError as exc:
            return f"HTTP {exc.code}: {exc.reason}"
        except Exception as exc:
            return f"FAILED: {exc}"

    def show_health_report(self) -> None:
        lines = []
        for service in self.services:
            lines.append(f"{service.label}: {self.fetch_url(service.url)}")
        messagebox.showinfo("AfriSync Health Check", "\n\n".join(lines))
        self.log("Health check completed.")

    def open_url(self, url: str) -> None:
        webbrowser.open(url)
        self.log(f"Opened {url}")

    def open_project_folder(self) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(self.project_root))  # type: ignore[attr-defined]
            else:
                webbrowser.open(self.project_root.as_uri())
        except Exception as exc:
            messagebox.showerror("Open folder failed", str(exc))

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        line = f"{timestamp}  {message}\n"
        try:
            self.log_text.insert(tk.END, line)
            self.log_text.see(tk.END)
        except AttributeError:
            pass

    def clear_logs(self) -> None:
        self.log_text.delete("1.0", tk.END)
        self.log("Logs cleared.")

    def on_close(self) -> None:
        running = [service.label for service in self.services if service.key in self.processes and self.processes[service.key].poll() is None]
        if running:
            answer = messagebox.askyesno(
                "Stop AfriSync services?",
                "These services are still running:\n\n"
                + "\n".join(running)
                + "\n\nStop them before closing the launcher?",
            )
            if answer:
                self.stop_all()
        self._closing = True
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = AfriSyncLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
