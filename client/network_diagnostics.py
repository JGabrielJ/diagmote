import platform
import re
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import dns.exception
import dns.resolver
import pandas as pd


class NetworkDiagnostics:
    """Perform active network connectivity diagnostics."""

    def __init__(self, output_dir: str | Path | None = None):
        project_root = Path(__file__).resolve().parent.parent

        self.output_dir = Path(output_dir or project_root / "data")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.output_file = self.output_dir / "connectivity_metrics.csv"

    def ping(self, host: str, count: int = 4, timeout: int = 2) -> dict:
        """Test host reachability and estimate packet loss and latency."""

        if count < 1 or timeout < 1:
            raise ValueError("Count and timeout must be positive integers.")

        system = platform.system().lower()

        if system == "windows":
            command_base = ["ping", "-n", "1", "-w", str(timeout * 1000)]
        elif system == "darwin":
            command_base = ["ping", "-c", "1", "-W", str(timeout * 1000)]
        elif system == "linux":
            command_base = ["ping", "-c", "1", "-W", str(timeout)]
        else:
            raise OSError(f"Unsupported operating system: {system}")

        latencies = []
        successful_probes = 0

        for _ in range(count):
            start = time.monotonic()

            try:
                result = subprocess.run(
                    [*command_base, host],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=timeout + 2,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                continue
            except FileNotFoundError:
                raise RuntimeError(
                    "The ping utility was not found on this system."
                )

            elapsed = (time.monotonic() - start) * 1000

            if result.returncode == 0:
                successful_probes += 1

                output = result.stdout + result.stderr
                match = re.search(
                    r"time[=<]\s*([\d.,]+)\s*ms",
                    output,
                    re.IGNORECASE,
                )

                if match:
                    latency = float(match.group(1).replace(",", "."))
                else:
                    latency = elapsed

                latencies.append(latency)

        packet_loss = ((count - successful_probes) / count) * 100
        average_latency = (
            round(sum(latencies) / len(latencies), 2) if latencies else None
        )

        return {
            "timestamp": datetime.now().astimezone().isoformat(),
            "check_type": "ping",
            "target": host,
            "success": successful_probes > 0,
            "latency_ms": average_latency,
            "packet_loss_percent": round(packet_loss, 2),
            "details": (f"{successful_probes}/{count} responses received"),
        }

    def check_dns(
        self,
        hostname: str,
        timeout: float = 2.0,
        lifetime: float = 5.0,
    ) -> dict:
        """Check whether a hostname can be resolved through DNS."""

        if timeout <= 0 or lifetime <= 0:
            raise ValueError("Timeout and lifetime must be positive.")

        start = time.perf_counter()

        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = timeout

            answers = resolver.resolve_name(
                hostname,
                family=socket.AF_UNSPEC,
                lifetime=lifetime,
            )

            resolved_addresses = sorted(set(answers.addresses()))

            success = bool(resolved_addresses)
            details = (
                ", ".join(resolved_addresses)
                if success
                else "No addresses returned."
            )

        except dns.exception.DNSException as error:
            success = False
            details = str(error)

        latency = round((time.perf_counter() - start) * 1000, 2)

        return {
            "timestamp": datetime.now().astimezone().isoformat(),
            "check_type": "dns",
            "target": hostname,
            "success": success,
            "latency_ms": latency,
            "packet_loss_percent": None,
            "details": details,
        }

    def check_tcp(self, host: str, port: int = 443, timeout: int = 5) -> dict:
        """Test whether a TCP connection can be established."""

        start = time.monotonic()

        try:
            with socket.create_connection(
                (host, port),
                timeout=timeout,
            ):
                latency = (time.monotonic() - start) * 1000
                success = True
                details = f"TCP connection established on port {port}."

        except OSError as error:
            latency = None
            success = False
            details = str(error)

        return {
            "timestamp": datetime.now().astimezone().isoformat(),
            "check_type": "tcp",
            "target": f"{host}:{port}",
            "success": success,
            "latency_ms": round(latency, 2) if latency is not None else None,
            "packet_loss_percent": None,
            "details": details,
        }

    def run_checks(self) -> list[dict]:
        """Run the default set of active connectivity tests."""

        return [
            self.ping("1.1.1.1"),
            self.check_dns("example.com"),
            self.check_tcp("example.com", 443),
        ]

    def save(self, results: list[dict]):
        """Append connectivity diagnostics to a CSV file."""

        if not results:
            return

        dataframe = pd.DataFrame(results)

        dataframe.to_csv(
            self.output_file,
            mode="a",
            header=not self.output_file.exists(),
            index=False,
        )

    def display(self, results: list[dict]):
        """Display connectivity diagnostic results."""

        if not results:
            print("\nNo connectivity diagnostic results available.")
            return

        print("\n========== CONNECTIVITY DIAGNOSTICS ==========")

        for result in results:
            status = "SUCCESS" if result["success"] else "FAILED"

            print(f"\nTest: {result['check_type'].upper()}")
            print(f"Target: {result['target']}")
            print(f"Status: {status}")

            if result["latency_ms"] is not None:
                print(f"Latency: {result['latency_ms']} ms")

            if result["packet_loss_percent"] is not None:
                print(f"Packet loss: {result['packet_loss_percent']}%")

            print(f"Details: {result['details']}")

        print("==============================================")
