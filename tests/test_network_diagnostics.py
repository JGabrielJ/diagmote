import socket
from contextlib import nullcontext
from types import SimpleNamespace

import pandas as pd
import pytest

import client.network_diagnostics as diagnostics_module
from client.network_diagnostics import NetworkDiagnostics


@pytest.fixture
def diagnostics(tmp_path):
    """Create diagnostics using an isolated temporary directory."""

    return NetworkDiagnostics(output_dir=tmp_path)


# --------------------------------------------------
#                   Initialization
# --------------------------------------------------


def test_diagnostics_initialization(tmp_path):
    diagnostics = NetworkDiagnostics(output_dir=tmp_path)

    assert diagnostics.output_dir == tmp_path
    assert diagnostics.output_dir.exists()
    assert diagnostics.output_file == tmp_path / "connectivity_metrics.csv"


# --------------------------------------------------
#                         Ping
# --------------------------------------------------


def test_ping_success(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.platform,
        "system",
        lambda: "Linux",
    )

    monkeypatch.setattr(
        diagnostics_module,
        "time",
        SimpleNamespace(monotonic=lambda: 10.0),
    )

    monkeypatch.setattr(
        diagnostics_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="64 bytes from 1.1.1.1: time=12.5 ms",
            stderr="",
        ),
    )

    result = diagnostics.ping("1.1.1.1", count=1)

    assert result["check_type"] == "ping"
    assert result["target"] == "1.1.1.1"
    assert result["success"] is True
    assert result["latency_ms"] == 12.5
    assert result["packet_loss_percent"] == 0.0
    assert result["details"] == "1/1 responses received"
    assert "timestamp" in result


def test_ping_partial_packet_loss(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.platform,
        "system",
        lambda: "Linux",
    )

    responses = iter(
        [
            SimpleNamespace(
                returncode=0,
                stdout="64 bytes from 1.1.1.1: time=10.0 ms",
                stderr="",
            ),
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="Request timed out.",
            ),
        ]
    )

    monkeypatch.setattr(
        diagnostics_module.subprocess,
        "run",
        lambda *args, **kwargs: next(responses),
    )

    result = diagnostics.ping("1.1.1.1", count=2)

    assert result["success"] is True
    assert result["latency_ms"] == 10.0
    assert result["packet_loss_percent"] == 50.0
    assert result["details"] == "1/2 responses received"


def test_ping_failure(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.platform,
        "system",
        lambda: "Linux",
    )

    monkeypatch.setattr(
        diagnostics_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Request timed out.",
        ),
    )

    result = diagnostics.ping("192.0.2.1", count=2)

    assert result["success"] is False
    assert result["latency_ms"] is None
    assert result["packet_loss_percent"] == 100.0
    assert result["details"] == "0/2 responses received"


def test_ping_timeout(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.platform,
        "system",
        lambda: "Linux",
    )

    def fake_run(*args, **kwargs):
        raise diagnostics_module.subprocess.TimeoutExpired(
            cmd="ping",
            timeout=4,
        )

    monkeypatch.setattr(
        diagnostics_module.subprocess,
        "run",
        fake_run,
    )

    result = diagnostics.ping("1.1.1.1", count=1)

    assert result["success"] is False
    assert result["latency_ms"] is None
    assert result["packet_loss_percent"] == 100.0


def test_ping_raises_error_when_utility_is_missing(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.platform,
        "system",
        lambda: "Linux",
    )

    monkeypatch.setattr(
        diagnostics_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError),
    )

    with pytest.raises(RuntimeError, match="ping utility was not found"):
        diagnostics.ping("1.1.1.1", count=1)


@pytest.mark.parametrize(
    ("count", "timeout"),
    [
        (0, 2),
        (-1, 2),
        (1, 0),
        (1, -1),
    ],
)
def test_ping_rejects_invalid_arguments(diagnostics, count, timeout):
    with pytest.raises(ValueError):
        diagnostics.ping(
            "1.1.1.1",
            count=count,
            timeout=timeout,
        )


def test_ping_rejects_unsupported_operating_system(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.platform,
        "system",
        lambda: "FreeBSD",
    )

    with pytest.raises(OSError, match="Unsupported operating system"):
        diagnostics.ping("1.1.1.1", count=1)


# --------------------------------------------------
#                         DNS
# --------------------------------------------------


def test_check_dns_success(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 0, 0, 0)),
        ],
    )

    result = diagnostics.check_dns("example.com")

    assert result["check_type"] == "dns"
    assert result["target"] == "example.com"
    assert result["success"] is True
    assert result["latency_ms"] is None
    assert result["packet_loss_percent"] is None
    assert result["details"] == "192.0.2.10, 2001:db8::1"


def test_check_dns_failure(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            socket.gaierror("Name or service not known")
        ),
    )

    result = diagnostics.check_dns("invalid.example")

    assert result["success"] is False
    assert result["latency_ms"] is None
    assert result["packet_loss_percent"] is None
    assert "Name or service not known" in result["details"]


def test_check_dns_without_returned_addresses(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [],
    )

    result = diagnostics.check_dns("example.com")

    assert result["success"] is False
    assert result["details"] == "No addresses returned."


# --------------------------------------------------
#                         TCP
# --------------------------------------------------


def test_check_tcp_success(diagnostics, monkeypatch):
    times = iter([10.0, 10.025])

    monkeypatch.setattr(
        diagnostics_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(times)),
    )

    monkeypatch.setattr(
        diagnostics_module.socket,
        "create_connection",
        lambda address, timeout: nullcontext(),
    )

    result = diagnostics.check_tcp("example.com", port=443)

    assert result["check_type"] == "tcp"
    assert result["target"] == "example.com:443"
    assert result["success"] is True
    assert result["latency_ms"] == 25.0
    assert result["packet_loss_percent"] is None
    assert result["details"] == "TCP connection established on port 443."


def test_check_tcp_failure(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("Connection refused")),
    )

    result = diagnostics.check_tcp("example.com", port=443)

    assert result["success"] is False
    assert result["latency_ms"] is None
    assert result["packet_loss_percent"] is None
    assert "Connection refused" in result["details"]


# --------------------------------------------------
#                   Combined checks
# --------------------------------------------------


def test_run_checks(diagnostics, monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "ping",
        lambda host: {"check_type": "ping", "target": host},
    )
    monkeypatch.setattr(
        diagnostics,
        "check_dns",
        lambda hostname: {"check_type": "dns", "target": hostname},
    )
    monkeypatch.setattr(
        diagnostics,
        "check_tcp",
        lambda host, port: {
            "check_type": "tcp",
            "target": f"{host}:{port}",
        },
    )

    results = diagnostics.run_checks()

    assert len(results) == 3
    assert results[0]["check_type"] == "ping"
    assert results[0]["target"] == "1.1.1.1"
    assert results[1]["check_type"] == "dns"
    assert results[1]["target"] == "example.com"
    assert results[2]["check_type"] == "tcp"
    assert results[2]["target"] == "example.com:443"


# --------------------------------------------------
#                     CSV storage
# --------------------------------------------------


def test_save_connectivity_metrics(diagnostics):
    results = [
        {
            "check_type": "ping",
            "target": "1.1.1.1",
            "success": True,
            "latency_ms": 12.5,
        }
    ]

    diagnostics.save(results)

    assert diagnostics.output_file.exists()

    dataframe = pd.read_csv(diagnostics.output_file)

    assert len(dataframe) == 1
    assert dataframe.iloc[0]["check_type"] == "ping"
    assert dataframe.iloc[0]["target"] == "1.1.1.1"
    assert dataframe.iloc[0]["success"] == True
    assert dataframe.iloc[0]["latency_ms"] == 12.5


def test_save_appends_connectivity_metrics(diagnostics):
    first_result = [
        {
            "check_type": "ping",
            "target": "1.1.1.1",
            "success": True,
        }
    ]

    second_result = [
        {
            "check_type": "dns",
            "target": "example.com",
            "success": True,
        }
    ]

    diagnostics.save(first_result)
    diagnostics.save(second_result)

    dataframe = pd.read_csv(diagnostics.output_file)

    assert len(dataframe) == 2
    assert dataframe.iloc[0]["check_type"] == "ping"
    assert dataframe.iloc[1]["check_type"] == "dns"


def test_save_empty_results(diagnostics):
    diagnostics.save([])

    assert not diagnostics.output_file.exists()


# --------------------------------------------------
#                    Terminal output
# --------------------------------------------------


def test_display(diagnostics, capsys):
    results = [
        {
            "check_type": "ping",
            "target": "1.1.1.1",
            "success": True,
            "latency_ms": 12.5,
            "packet_loss_percent": 0.0,
            "details": "4/4 responses received",
        },
        {
            "check_type": "dns",
            "target": "example.com",
            "success": False,
            "latency_ms": None,
            "packet_loss_percent": None,
            "details": "Name or service not known",
        },
    ]

    diagnostics.display(results)

    output = capsys.readouterr().out

    assert "CONNECTIVITY DIAGNOSTICS" in output
    assert "PING" in output
    assert "1.1.1.1" in output
    assert "SUCCESS" in output
    assert "12.5 ms" in output
    assert "DNS" in output
    assert "example.com" in output
    assert "FAILED" in output
    assert "Name or service not known" in output


def test_display_empty_results(diagnostics, capsys):
    diagnostics.display([])

    output = capsys.readouterr().out

    assert "No connectivity diagnostic results available." in output
