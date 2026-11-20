import tempfile
from pathlib import Path

import pandas as pd
from behave import given, then, when

from client.collector import SystemCollector


@given("que o agente de monitoramento está configurado")
def step_configure_monitoring_agent(context):
    context.temp_dir = tempfile.TemporaryDirectory()

    context.output_dir = Path(context.temp_dir.name)

    context.collector = SystemCollector(output_dir=context.output_dir)


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
