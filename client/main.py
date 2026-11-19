import time
from threading import Event, Thread

from client.collector import SystemCollector
from client.network_diagnostics import NetworkDiagnostics


def monitoring_task(
    stop_event,
    collector,
    network_diagnostics,
    interval: int = 5,
    process_interval: int = 15,
    connectivity_interval: int = 60,
):
    """Periodically collect system, process and network information."""

    collector.initialize_cpu_measurement()

    last_process_collection = 0.0
    last_connectivity_collection = 0.0

    while not stop_event.wait(interval):
        # Collect general system metrics
        metrics = collector.collect()

        collector.save(metrics)
        collector.display(metrics)

        # Collect network information
        network_data = collector.collect_network()

        collector.save_network(network_data)
        collector.display_network(network_data)

        current_time = time.monotonic()

        # Collect process information
        if current_time - last_process_collection >= process_interval:
            processes = collector.collect_processes()

            collector.save_processes(processes)
            collector.display_processes(processes)

            last_process_collection = current_time

        # Run active connectivity diagnostics
        if current_time - last_connectivity_collection >= connectivity_interval:
            results = network_diagnostics.run_checks()

            network_diagnostics.save(results)
            network_diagnostics.display(results)

            last_connectivity_collection = current_time


def main():
    collector = SystemCollector()
    network_diagnostics = NetworkDiagnostics()
    stop_event = Event()

    monitoring_thread = Thread(
        target=monitoring_task,
        args=(stop_event, collector, network_diagnostics),
        name="DiagmoteMonitor",
    )

    print("Diagmote System Monitor started.")
    print("Press CTRL+C to stop.\n")

    monitoring_thread.start()

    try:
        while monitoring_thread.is_alive():
            monitoring_thread.join(timeout=1)

    except KeyboardInterrupt:
        print("\nStopping Diagmote...")

    finally:
        stop_event.set()
        monitoring_thread.join()

    print("Monitoring stopped.")


if __name__ == "__main__":
    main()
