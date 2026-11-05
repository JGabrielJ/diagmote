import platform
import socket
from datetime import datetime
from pathlib import Path

import pandas as pd
import psutil


class SystemCollector:
    """Collects and stores system diagnostic information."""

    def __init__(self, output_dir: str | Path | None = None):
        project_root = Path(__file__).resolve().parent.parent

        self.output_dir = Path(output_dir or project_root / "data")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.output_file = self.output_dir / "system_metrics.csv"

    def initialize_cpu_measurement(self):
        """Initialize CPU measurement in the current thread."""

        psutil.cpu_percent(interval=None)

    def collect_system_info(self) -> dict:
        """Collect general information about the computer."""

        return {
            "timestamp": datetime.now().astimezone().isoformat(),
            "hostname": socket.gethostname(),
            "operating_system": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
        }

    def collect_cpu(self) -> dict:
        """Collect CPU usage information."""

        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
        }

    def collect_memory(self) -> dict:
        """Collect RAM usage information."""

        memory = psutil.virtual_memory()

        return {
            "memory_percent": memory.percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_available_gb": round(memory.available / (1024**3), 2),
        }

    def collect_disk(self) -> dict:
        """Collect disk usage information."""

        disk = psutil.disk_usage(str(Path.home().anchor))

        return {
            "disk_percent": disk.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
        }

    def collect(self) -> dict:
        """Collect all available system metrics."""

        metrics = {
            **self.collect_system_info(),
            **self.collect_cpu(),
            **self.collect_memory(),
            **self.collect_disk(),
        }

        return metrics

    def save(self, metrics: dict):
        """Append metrics to a CSV file."""

        dataframe = pd.DataFrame([metrics])

        dataframe.to_csv(
            self.output_file,
            mode="a",
            header=not self.output_file.exists(),
            index=False,
        )

    def display(self, metrics: dict):
        """Display collected metrics."""

        print("\n========== DIAGMOTE ==========")
        print(f"Computer: {metrics['hostname']}")
        print(f"OS: {metrics['operating_system']} ({metrics['architecture']})")
        print(f"Processor: {metrics['processor']}")
        print(f"CPU: {metrics['cpu_percent']}%")
        print(
            f"RAM: {metrics['memory_percent']}% "
            f"({metrics['memory_available_gb']} GB available)"
        )
        print(f"Disk: {metrics['disk_percent']}% ({metrics['disk_free_gb']} GB free)")
        print("==============================")

    def collect_processes(self) -> list[dict]:
        """Collect information about running processes."""

        timestamp = datetime.now().astimezone().isoformat()
        processes = []

        for process in psutil.process_iter(attrs=["pid", "name", "status"]):
            try:
                with process.oneshot():
                    memory_info = process.memory_info()

                    process_data = {
                        "timestamp": timestamp,
                        "pid": process.info["pid"],
                        "name": process.info["name"],
                        "status": process.info["status"],
                        "cpu_percent": process.cpu_percent(interval=None),
                        "memory_percent": process.memory_percent(),
                        "memory_mb": round(memory_info.rss / (1024**2), 2),
                    }

                    processes.append(process_data)
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        return processes

    def save_processes(self, processes: list[dict]):
        """Append process information to a CSV file."""

        if not processes:
            return

        output_file = self.output_dir / "process_metrics.csv"

        dataframe = pd.DataFrame(processes)

        dataframe.to_csv(
            output_file,
            mode="a",
            header=not output_file.exists(),
            index=False,
        )

    def display_processes(self, processes: list[dict], limit: int = 5):
        """Display the processes with the highest RAM usage."""

        if not processes:
            print("\nNo process information available.")
            return

        top_processes = sorted(
            processes,
            key=lambda process: process["memory_percent"],
            reverse=True,
        )[:limit]

        print("\n========== TOP PROCESSES ==========")
        print(f"{'PID':<10}{'NAME':<25}{'CPU (%)':<12}{'RAM (%)':<12}")

        for process in top_processes:
            name = (process["name"] or "Unknown")[:24]

            print(
                f"{process['pid']:<10}"
                f"{name:<25}"
                f"{process['cpu_percent']:<12.1f}"
                f"{process['memory_percent']:<12.2f}"
            )

        print("===================================")
