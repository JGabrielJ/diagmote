import time
from threading import Event, Thread

from client.collector import SystemCollector


def monitoring_task(
    stop_event: Event,
    collector: SystemCollector,
    interval: int = 5,
    process_interval: int = 15,
):
    """Periodically collect system information."""

    collector.initialize_cpu_measurement()

    last_process_collection = 0.0

    while not stop_event.wait(interval):
        # Collect general system metrics
        metrics = collector.collect()

        collector.save(metrics)
        collector.display(metrics)

        # Collect process information at a separate interval
        current_time = time.monotonic()

        if current_time - last_process_collection >= process_interval:
            processes = collector.collect_processes()

            collector.save_processes(processes)
            collector.display_processes(processes)

            last_process_collection = current_time


def main():
    collector = SystemCollector()
    stop_event = Event()

    monitoring_thread = Thread(
        target=monitoring_task,
        args=(stop_event, collector),
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
