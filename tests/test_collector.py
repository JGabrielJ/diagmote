"""
Diagmote - SystemCollector monitoring tests.
Copyright (C) 2026 Gabriel Jacinto

Diagmote is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Diagmote is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Diagmote. If not, see <https://www.gnu.org/licenses/>.
"""

import builtins
import io
import socket
import typing
from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import psutil
import pytest

import client.collector as collector_module
from client.collector import SystemCollector


@pytest.fixture
def collector(tmp_path):
    """Create a collector using an isolated temporary directory."""

    return SystemCollector(output_dir=tmp_path)


# --------------------------------------------------
#                   Initialization
# --------------------------------------------------


def test_collector_initialization(tmp_path):
    collector = SystemCollector(output_dir=tmp_path)

    assert collector.output_dir == tmp_path
    assert collector.output_dir.exists()
    assert collector.output_file == tmp_path / "system_metrics.csv"


def test_initialize_cpu_measurement(collector, monkeypatch):
    calls = []

    monkeypatch.setattr(
        collector_module.psutil,
        "cpu_percent",
        lambda interval=None: calls.append(interval),
    )

    collector.initialize_cpu_measurement()

    assert calls == [None]


# --------------------------------------------------
#               Processor information
# --------------------------------------------------


def test_collect_processor_info_linux(collector, monkeypatch):
    monkeypatch.setattr(collector_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(collector_module.platform, "processor", lambda: "")
    monkeypatch.setattr(
        collector_module.platform,
        "uname",
        lambda: SimpleNamespace(processor="fallback"),
    )

    monkeypatch.setattr(
        builtins,
        "open",
        lambda *args, **kwargs: io.StringIO(
            "processor : 0\nmodel name : Test Processor\n"
        ),
    )

    monkeypatch.setattr(
        collector_module.psutil,
        "cpu_freq",
        lambda: SimpleNamespace(current=3200.123),
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "cpu_count",
        lambda logical=True: 8 if logical else 4,
    )

    result = collector.collect_processor_info()

    assert result["processor"] == "Test Processor"
    assert result["cpu_physical_cores"] == 4
    assert result["cpu_logical_cores"] == 8
    assert result["cpu_frequency_mhz"] == 3200.12


def test_collect_processor_info_when_cpuinfo_is_unavailable(
    collector,
    monkeypatch,
):
    monkeypatch.setattr(collector_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(collector_module.platform, "processor", lambda: "")
    monkeypatch.setattr(
        collector_module.platform,
        "uname",
        lambda: SimpleNamespace(processor="Fallback CPU"),
    )
    monkeypatch.setattr(
        builtins,
        "open",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("Permission denied")
        ),
    )
    monkeypatch.setattr(collector_module.psutil, "cpu_freq", lambda: None)
    monkeypatch.setattr(
        collector_module.psutil,
        "cpu_count",
        lambda logical=True: 4,
    )

    result = collector.collect_processor_info()

    assert result["processor"] == "Fallback CPU"
    assert result["cpu_frequency_mhz"] is None


def test_collect_processor_info_without_frequency(collector, monkeypatch):
    monkeypatch.setattr(
        collector_module.platform,
        "system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        collector_module.platform,
        "processor",
        lambda: "Test CPU",
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "cpu_freq",
        lambda: None,
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "cpu_count",
        lambda logical=True: 4,
    )

    result = collector.collect_processor_info()

    assert result["processor"] == "Test CPU"
    assert result["cpu_frequency_mhz"] is None


# --------------------------------------------------
#                       Uptime
# --------------------------------------------------


def test_collect_uptime(collector, monkeypatch):
    monkeypatch.setattr(
        collector_module.psutil,
        "boot_time",
        lambda: 1000,
    )
    monkeypatch.setattr(
        collector_module,
        "time",
        SimpleNamespace(time=lambda: 4600),
    )

    result = collector.collect_uptime()

    assert result["uptime_seconds"] == 3600
    assert isinstance(
        datetime.fromisoformat(result["boot_time"]),
        datetime,
    )


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0d 0h 0min 0s"),
        (59, "0d 0h 0min 59s"),
        (60, "0d 0h 1min 0s"),
        (3600, "0d 1h 0min 0s"),
        (86400, "1d 0h 0min 0s"),
        (90061, "1d 1h 1min 1s"),
    ],
)
def test_format_uptime(collector, seconds, expected):
    assert collector.format_uptime(seconds) == expected


# --------------------------------------------------
#             General system information
# --------------------------------------------------


def test_collect_system_info(collector, monkeypatch):
    monkeypatch.setattr(
        collector_module.platform,
        "system",
        lambda: "Linux",
    )
    monkeypatch.setattr(
        collector_module.platform,
        "freedesktop_os_release",
        lambda: {"PRETTY_NAME": "Test Linux"},
    )
    monkeypatch.setattr(
        collector_module.platform,
        "version",
        lambda: "Test version",
    )
    monkeypatch.setattr(
        collector_module.platform,
        "release",
        lambda: "Test release",
    )
    monkeypatch.setattr(
        collector_module.platform,
        "machine",
        lambda: "x86_64",
    )
    monkeypatch.setattr(
        collector_module.socket,
        "gethostname",
        lambda: "test-machine",
    )

    monkeypatch.setattr(
        collector,
        "collect_processor_info",
        lambda: {"processor": "Test CPU"},
    )
    monkeypatch.setattr(
        collector,
        "collect_uptime",
        lambda: {
            "boot_time": "2026-01-01T00:00:00-03:00",
            "uptime_seconds": 3600,
        },
    )

    result = collector.collect_system_info()

    assert result["hostname"] == "test-machine"
    assert result["operating_system"] == "Linux"
    assert result["distribution"] == "Test Linux"
    assert result["os_version"] == "Test version"
    assert result["os_release"] == "Test release"
    assert result["architecture"] == "x86_64"
    assert result["processor"] == "Test CPU"
    assert result["uptime_seconds"] == 3600
    assert "timestamp" in result


@pytest.mark.parametrize(
    "error",
    [
        AttributeError("Function unavailable"),
        OSError("Unable to read OS information"),
    ],
)
def test_collect_system_info_when_os_release_fails(
    collector,
    monkeypatch,
    error,
):
    monkeypatch.setattr(collector_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        collector_module.platform,
        "freedesktop_os_release",
        lambda: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr(
        collector_module.socket,
        "gethostname",
        lambda: "test-machine",
    )
    monkeypatch.setattr(collector_module.platform, "version", lambda: "1.0")
    monkeypatch.setattr(collector_module.platform, "release", lambda: "1.0")
    monkeypatch.setattr(collector_module.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        collector,
        "collect_processor_info",
        lambda: {"processor": "Test CPU"},
    )
    monkeypatch.setattr(
        collector,
        "collect_uptime",
        lambda: {
            "boot_time": "2026-01-01T00:00:00-03:00",
            "uptime_seconds": 60,
        },
    )

    result = collector.collect_system_info()

    assert result["operating_system"] == "Linux"
    assert result["distribution"] == "Linux"


# --------------------------------------------------
#                CPU, memory and disk
# --------------------------------------------------


def test_collect_cpu(collector, monkeypatch):
    monkeypatch.setattr(
        collector_module.psutil,
        "cpu_percent",
        lambda interval=None: 25.5,
    )

    result = collector.collect_cpu()

    assert result == {"cpu_percent": 25.5}


def test_collect_memory(collector, monkeypatch):
    monkeypatch.setattr(
        collector_module.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            percent=50.0,
            total=8 * 1024**3,
            available=4 * 1024**3,
        ),
    )

    result = collector.collect_memory()

    assert result["memory_percent"] == 50.0
    assert result["memory_total_gb"] == 8.0
    assert result["memory_available_gb"] == 4.0


def test_collect_disk(collector, monkeypatch):
    monkeypatch.setattr(
        collector_module.psutil,
        "disk_usage",
        lambda path: SimpleNamespace(
            percent=60.0,
            total=256 * 1024**3,
            free=100 * 1024**3,
        ),
    )

    result = collector.collect_disk()

    assert result["disk_percent"] == 60.0
    assert result["disk_total_gb"] == 256.0
    assert result["disk_free_gb"] == round(100.0, 2)


# --------------------------------------------------
#                 Network collection
# --------------------------------------------------


def test_collect_network(collector, monkeypatch):
    counters = SimpleNamespace(
        bytes_sent=1000,
        bytes_recv=2000,
        packets_sent=10,
        packets_recv=20,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
    )

    monkeypatch.setattr(
        collector_module.psutil,
        "net_if_addrs",
        lambda: {
            "eth0": [
                SimpleNamespace(
                    family=socket.AF_INET,
                    address="192.0.2.10",
                )
            ]
        },
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_if_stats",
        lambda: {
            "eth0": SimpleNamespace(
                isup=True,
                speed=1000,
                mtu=1500,
            )
        },
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_io_counters",
        lambda pernic=True: {"eth0": counters},
    )
    monkeypatch.setattr(
        collector_module,
        "time",
        SimpleNamespace(monotonic=lambda: 10.0),
    )

    result = collector.collect_network()

    assert len(result) == 1
    assert result[0]["interface"] == "eth0"
    assert result[0]["is_up"] is True
    assert result[0]["ipv4_addresses"] == "192.0.2.10"
    assert result[0]["bytes_sent_per_sec"] == 0.0
    assert result[0]["bytes_recv_per_sec"] == 0.0


def test_collect_network_calculates_traffic_rates(collector, monkeypatch):
    counters = SimpleNamespace(
        bytes_sent=1000,
        bytes_recv=2000,
        packets_sent=10,
        packets_recv=20,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
    )

    monkeypatch.setattr(
        collector_module.psutil, "net_if_addrs", lambda: {"eth0": []}
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_if_stats",
        dict,
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_io_counters",
        lambda pernic=True: {"eth0": counters},
    )

    times = iter([10.0, 12.0])

    monkeypatch.setattr(
        collector_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(times)),
    )

    first_result = collector.collect_network()

    counters.bytes_sent = 1200
    counters.bytes_recv = 2400

    second_result = collector.collect_network()

    assert first_result[0]["bytes_sent_per_sec"] == 0.0
    assert second_result[0]["bytes_sent_per_sec"] == 100.0
    assert second_result[0]["bytes_recv_per_sec"] == 200.0


def test_collect_network_skips_interfaces_without_counters(
    collector,
    monkeypatch,
):
    monkeypatch.setattr(
        collector_module.psutil,
        "net_if_addrs",
        lambda: {"eth0": []},
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_if_stats",
        dict,
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_io_counters",
        lambda pernic=True: {},
    )

    result = collector.collect_network()

    assert result == []


def test_collect_network_handles_zero_elapsed_time(collector, monkeypatch):
    counters = SimpleNamespace(
        bytes_sent=1000,
        bytes_recv=2000,
        packets_sent=10,
        packets_recv=20,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
    )

    monkeypatch.setattr(
        collector_module.psutil,
        "net_if_addrs",
        lambda: {"eth0": []},
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_if_stats",
        dict,
    )
    monkeypatch.setattr(
        collector_module.psutil,
        "net_io_counters",
        lambda pernic=True: {"eth0": counters},
    )
    monkeypatch.setattr(
        collector_module,
        "time",
        SimpleNamespace(monotonic=lambda: 10.0),
    )

    collector.collect_network()
    result = collector.collect_network()

    assert result[0]["bytes_sent_per_sec"] == 0.0
    assert result[0]["bytes_recv_per_sec"] == 0.0


# --------------------------------------------------
#                 Process collection
# --------------------------------------------------


def test_collect_processes(collector, monkeypatch):
    class FakeProcess:
        info: typing.ClassVar = {
            "pid": 1234,
            "name": "test-process",
            "status": "running",
        }

        def oneshot(self):
            return nullcontext()

        def memory_info(self):
            return SimpleNamespace(rss=2 * 1024**2)

        def cpu_percent(self, interval=None):
            return 10.0

        def memory_percent(self):
            return 2.5

    monkeypatch.setattr(
        collector_module.psutil,
        "process_iter",
        lambda attrs=None: [FakeProcess()],
    )

    result = collector.collect_processes()

    assert len(result) == 1
    assert result[0]["pid"] == 1234
    assert result[0]["name"] == "test-process"
    assert result[0]["status"] == "running"
    assert result[0]["cpu_percent"] == 10.0
    assert result[0]["memory_percent"] == 2.5
    assert result[0]["memory_mb"] == 2.0


@pytest.mark.parametrize(
    "error",
    [
        psutil.NoSuchProcess(1234),
        psutil.AccessDenied(1234),
        psutil.ZombieProcess(1234),
    ],
)
def test_collect_processes_skips_unavailable_processes(
    collector,
    monkeypatch,
    error,
):
    class FakeProcess:
        def oneshot(self):
            raise error

    monkeypatch.setattr(
        collector_module.psutil,
        "process_iter",
        lambda attrs=None: [FakeProcess()],
    )

    result = collector.collect_processes()

    assert result == []


# --------------------------------------------------
#                Combined collection
# --------------------------------------------------


def test_collect_combines_all_metrics(collector, monkeypatch):
    monkeypatch.setattr(
        collector,
        "collect_system_info",
        lambda: {"hostname": "test-machine"},
    )
    monkeypatch.setattr(
        collector,
        "collect_cpu",
        lambda: {"cpu_percent": 20.0},
    )
    monkeypatch.setattr(
        collector,
        "collect_memory",
        lambda: {"memory_percent": 40.0},
    )
    monkeypatch.setattr(
        collector,
        "collect_disk",
        lambda: {"disk_percent": 60.0},
    )

    result = collector.collect()

    assert result == {
        "hostname": "test-machine",
        "cpu_percent": 20.0,
        "memory_percent": 40.0,
        "disk_percent": 60.0,
    }


# --------------------------------------------------
#                    CSV storage
# --------------------------------------------------


def test_save_system_metrics(collector):
    metrics = {
        "hostname": "test-machine",
        "cpu_percent": 25.0,
    }

    collector.save(metrics)

    assert collector.output_file.exists()

    dataframe = pd.read_csv(collector.output_file)

    assert len(dataframe) == 1
    assert dataframe.iloc[0]["hostname"] == "test-machine"
    assert dataframe.iloc[0]["cpu_percent"] == 25.0


def test_save_network_metrics(collector):
    network_data = [
        {
            "interface": "eth0",
            "bytes_sent": 1000,
        }
    ]

    collector.save_network(network_data)

    output_file = collector.output_dir / "network_metrics.csv"

    assert output_file.exists()
    assert pd.read_csv(output_file).iloc[0]["interface"] == "eth0"


def test_save_process_metrics(collector):
    processes = [
        {
            "pid": 1234,
            "name": "test-process",
        }
    ]

    collector.save_processes(processes)

    output_file = collector.output_dir / "process_metrics.csv"

    assert output_file.exists()
    assert pd.read_csv(output_file).iloc[0]["pid"] == 1234


def test_save_empty_network_data(collector):
    collector.save_network([])

    output_file = collector.output_dir / "network_metrics.csv"

    assert not output_file.exists()


def test_save_empty_process_data(collector):
    collector.save_processes([])

    output_file = collector.output_dir / "process_metrics.csv"

    assert not output_file.exists()


# --------------------------------------------------
#                  Terminal output
# --------------------------------------------------


def test_display(collector, capsys):
    metrics = {
        "hostname": "test-machine",
        "distribution": "Test Linux",
        "os_release": "1.0",
        "architecture": "x86_64",
        "processor": "Test CPU",
        "cpu_physical_cores": 4,
        "cpu_logical_cores": 8,
        "cpu_frequency_mhz": 3200.0,
        "cpu_percent": 20.0,
        "memory_percent": 40.0,
        "memory_available_gb": 4.0,
        "disk_percent": 60.0,
        "disk_free_gb": 100.0,
        "boot_time": "2026-01-01T00:00:00-03:00",
        "uptime_seconds": 3600,
    }

    collector.display(metrics)

    output = capsys.readouterr().out

    assert "test-machine" in output
    assert "Test Linux" in output
    assert "Test CPU" in output
    assert "Uptime: 0d 1h 0min 0s" in output


def test_display_network(collector, capsys):
    network_data = [
        {
            "interface": "eth0",
            "is_up": True,
            "ipv4_addresses": "192.0.2.10",
            "ipv6_addresses": "2001:db8::1",
            "bytes_recv_per_sec": 1024.0,
            "bytes_sent_per_sec": 512.0,
            "mtu": 1500,
            "speed_mbps": 1000,
        },
        {
            "interface": "wlan0",
            "is_up": False,
            "ipv4_addresses": "",
            "ipv6_addresses": "",
            "bytes_recv_per_sec": 0.0,
            "bytes_sent_per_sec": 0.0,
            "mtu": None,
            "speed_mbps": None,
        },
    ]

    collector.display_network(network_data)

    output = capsys.readouterr().out

    assert "NETWORK MONITOR" in output
    assert "Interface: eth0" in output
    assert "Interface: wlan0" in output
    assert "Status: UP" in output
    assert "Status: DOWN" in output
    assert "192.0.2.10" in output
    assert "2001:db8::1" in output
    assert "IPv4: N/A" in output
    assert "IPv6: N/A" in output
    assert "Download: 1024.00 B/s" in output
    assert "Upload: 512.00 B/s" in output
    assert "MTU: 1500" in output
    assert "Speed: 1000 Mbps" in output
    assert "MTU: N/A" in output
    assert "Speed: N/A" in output


def test_display_network_empty(collector, capsys):
    collector.display_network([])

    output = capsys.readouterr().out

    assert "No network information available." in output


def test_display_processes(collector, capsys):
    processes = [
        {
            "pid": 100,
            "name": "Low Usage",
            "cpu_percent": 5.0,
            "memory_percent": 1.0,
        },
        {
            "pid": 200,
            "name": "High Usage",
            "cpu_percent": 25.0,
            "memory_percent": 8.0,
        },
        {
            "pid": 300,
            "name": None,
            "cpu_percent": 10.0,
            "memory_percent": 4.0,
        },
        {
            "pid": 400,
            "name": "A Very Long Process Name That Exceeds The Limit",
            "cpu_percent": 15.0,
            "memory_percent": 2.0,
        },
    ]

    collector.display_processes(processes, limit=3)

    output = capsys.readouterr().out

    assert "TOP PROCESSES" in output
    assert "High Usage" in output
    assert "Unknown" in output
    assert "Low Usage" not in output
    assert "100" not in output
    assert "200" in output
    assert "300" in output
    assert "A Very Long Process Nam" in output
    assert "A Very Long Process Name That Exceeds The Limit" not in output


def test_display_processes_empty(collector, capsys):
    collector.display_processes([])

    output = capsys.readouterr().out

    assert "No process information available." in output
