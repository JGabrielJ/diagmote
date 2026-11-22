"""
Diagmote - Behavior-driven tests.
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

import tempfile
from pathlib import Path

import pandas as pd
from behave import given, then, when

from client.collector import SystemCollector
from client.network_diagnostics import NetworkDiagnostics


@given("que o agente de monitoramento está configurado")
def step_configure_monitoring_agent(context):
    context.temp_dir = tempfile.TemporaryDirectory()

    context.output_dir = Path(context.temp_dir.name)

    context.collector = SystemCollector(output_dir=context.output_dir)


# --------------------------------------------------
#                 Metrics monitoring
# --------------------------------------------------


@when("um ciclo de coleta de métricas é executado")
def step_execute_monitoring_cycle(context):
    context.metrics = context.collector.collect()

    context.collector.save(context.metrics)


@then("as métricas do sistema devem ser coletadas")
def step_verify_collected_metrics(context):
    assert context.metrics is not None
    assert isinstance(context.metrics, dict)
    assert len(context.metrics) > 0


@then("os dados devem ser armazenados em um arquivo CSV")
def step_verify_saved_metrics(context):
    csv_path = context.output_dir / "system_metrics.csv"

    assert csv_path.exists(), "O arquivo CSV não foi criado."

    saved_data = pd.read_csv(csv_path)

    assert not saved_data.empty, "O arquivo CSV está vazio."


# --------------------------------------------------
#                 Process monitoring
# --------------------------------------------------


@when("as informações dos processos em execução são coletadas")
def step_collect_processes(context):
    context.processes = context.collector.collect_processes()

    context.collector.save_processes(context.processes)


@then("a coleta deve retornar uma lista de processos")
def step_verify_processes(context):
    assert isinstance(context.processes, list)

    required_fields = {
        "timestamp",
        "pid",
        "name",
        "status",
        "cpu_percent",
        "memory_percent",
        "memory_mb",
    }

    for process in context.processes:
        assert required_fields.issubset(process.keys())


@then(
    "as informações dos processos disponíveis devem ser armazenadas em um arquivo CSV"
)
def step_verify_saved_processes(context):
    csv_path = context.output_dir / "process_metrics.csv"

    if context.processes:
        assert csv_path.exists(), "O arquivo CSV não foi criado."

        saved_data = pd.read_csv(csv_path)

        assert not saved_data.empty
        assert "pid" in saved_data.columns
        assert "name" in saved_data.columns
        assert len(saved_data) == len(context.processes)
    else:
        assert not csv_path.exists()


# --------------------------------------------------
#                  Network monitoring
# --------------------------------------------------


@when("as informações das interfaces de rede são coletadas")
def step_collect_network(context):
    context.network_data = context.collector.collect_network()

    context.collector.save_network(context.network_data)


@then("a coleta deve retornar uma lista de interfaces de rede")
def step_verify_network(context):
    assert isinstance(context.network_data, list)

    required_fields = {
        "timestamp",
        "interface",
        "is_up",
        "ipv4_addresses",
        "ipv6_addresses",
        "bytes_sent",
        "bytes_recv",
        "bytes_sent_per_sec",
        "bytes_recv_per_sec",
    }

    for interface in context.network_data:
        assert required_fields.issubset(interface.keys())


@then(
    "os dados das interfaces disponíveis devem ser armazenados em um arquivo CSV"
)
def step_verify_saved_network(context):
    csv_path = context.output_dir / "network_metrics.csv"

    if context.network_data:
        assert csv_path.exists(), "O arquivo CSV não foi criado."

        saved_data = pd.read_csv(csv_path)

        assert not saved_data.empty
        assert "interface" in saved_data.columns
        assert "bytes_sent" in saved_data.columns
        assert "bytes_recv" in saved_data.columns
        assert len(saved_data) == len(context.network_data)
    else:
        assert not csv_path.exists()


# --------------------------------------------------
#              Connectivity diagnostics
# --------------------------------------------------


@given("que o diagnóstico de conectividade está configurado")
def step_configure_connectivity_diagnostics(context):
    context.temp_dir = tempfile.TemporaryDirectory()
    context.output_dir = Path(context.temp_dir.name)

    context.diagnostics = NetworkDiagnostics(output_dir=context.output_dir)


@when("uma verificação de conectividade falha")
def step_connectivity_check_fails(context):
    def failed_ping(host):
        return {
            "timestamp": "2026-11-20T10:00:00",
            "check_type": "ping",
            "target": host,
            "success": False,
            "latency_ms": None,
            "packet_loss_percent": 100.0,
            "details": "0/4 responses received",
        }

    def successful_dns(hostname):
        return {
            "timestamp": "2026-11-20T10:00:00",
            "check_type": "dns",
            "target": hostname,
            "success": True,
            "latency_ms": 1.5,
            "packet_loss_percent": None,
            "details": "DNS resolution successful",
        }

    def successful_tcp(host, port=443):
        return {
            "timestamp": "2026-11-20T10:00:00",
            "check_type": "tcp",
            "target": f"{host}:{port}",
            "success": True,
            "latency_ms": 10.0,
            "packet_loss_percent": None,
            "details": "TCP connection successful",
        }

    context.diagnostics.ping = failed_ping
    context.diagnostics.check_dns = successful_dns
    context.diagnostics.check_tcp = successful_tcp

    context.results = context.diagnostics.run_checks()
    context.diagnostics.save(context.results)


@then("o resultado deve indicar uma falha")
def step_verify_connectivity_failure(context):
    assert context.results, "No connectivity results were returned."

    failures = [result for result in context.results if not result["success"]]

    assert failures, "No connectivity failure was detected."


@then("a falha deve ser registrada em um arquivo CSV")
def step_verify_connectivity_failure_csv(context):
    csv_path = context.output_dir / "connectivity_metrics.csv"

    assert csv_path.exists(), "Connectivity CSV file was not created."

    data = pd.read_csv(csv_path)

    assert not data.empty, "Connectivity CSV file is empty."

    failures = data[data["success"] == False]

    assert not failures.empty, "No failure was recorded in the CSV."
