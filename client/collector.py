import platform
import socket
import time
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

        self._network_previous = {}

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

    def collect_network(self) -> list[dict]:
        """Collect network interface information and traffic."""

        timestamp = datetime.now().astimezone().isoformat()
        current_time = time.monotonic()

        addresses = psutil.net_if_addrs()
        interface_stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)

        interfaces = set(addresses) | set(interface_stats) | set(io_counters)

        network_data = []

        for interface in sorted(interfaces):
            stats = interface_stats.get(interface)
            counters = io_counters.get(interface)

            if counters is None:
                continue

            interface_addresses = addresses.get(interface, [])

            ipv4_addresses = [
                address.address
                for address in interface_addresses
                if address.family == socket.AF_INET
            ]

            ipv6_addresses = [
                address.address
                for address in interface_addresses
                if address.family == socket.AF_INET6
            ]

            previous = self._network_previous.get(interface)

            if previous:
                previous_sent, previous_recv, previous_time = previous
                elapsed = current_time - previous_time

                if elapsed > 0:
                    sent_rate = (counters.bytes_sent - previous_sent) / elapsed
                    recv_rate = (counters.bytes_recv - previous_recv) / elapsed
                else:
                    sent_rate = 0.0
                    recv_rate = 0.0
            else:
                sent_rate = 0.0
                recv_rate = 0.0

            self._network_previous[interface] = (
                counters.bytes_sent,
                counters.bytes_recv,
                current_time,
            )

            network_data.append(
                {
                    "timestamp": timestamp,
                    "interface": interface,
                    "is_up": stats.isup if stats else None,
                    "speed_mbps": stats.speed if stats else None,
                    "mtu": stats.mtu if stats else None,
                    "ipv4_addresses": "; ".join(ipv4_addresses),
                    "ipv6_addresses": "; ".join(ipv6_addresses),
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "bytes_sent_per_sec": round(sent_rate, 2),
                    "bytes_recv_per_sec": round(recv_rate, 2),
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                    "errors_in": counters.errin,
                    "errors_out": counters.errout,
                    "drops_in": counters.dropin,
                    "drops_out": counters.dropout,
                }
            )

        return network_data

    def save_network(self, network_data: list[dict]):
        """Append network information to a CSV file."""

        if not network_data:
            return

        output_file = self.output_dir / "network_metrics.csv"

        dataframe = pd.DataFrame(network_data)

        dataframe.to_csv(
            output_file,
            mode="a",
            header=not output_file.exists(),
            index=False,
        )

    def display_network(self, network_data: list[dict]):
        """Display network interface information."""

        if not network_data:
            print("\nNo network information available.")
            return

        print("\n========== NETWORK MONITOR ==========")

        for interface in network_data:
            status = "UP" if interface["is_up"] else "DOWN"

            print(f"\nInterface: {interface['interface']}")
            print(f"Status: {status}")
            print(f"IPv4: {interface['ipv4_addresses'] or 'N/A'}")
            print(f"IPv6: {interface['ipv6_addresses'] or 'N/A'}")

            print(f"Download: {interface['bytes_recv_per_sec']:.2f} B/s")
            print(f"Upload: {interface['bytes_sent_per_sec']:.2f} B/s")

            print(
                f"MTU: {interface['mtu'] or 'N/A'} | "
                f"Speed: {interface['speed_mbps'] or 'N/A'} Mbps"
            )

        print("=====================================")

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
