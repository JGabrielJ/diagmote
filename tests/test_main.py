from types import SimpleNamespace

import client.main as main_module
from client.main import monitoring_task


class FakeStopEvent:
    """Simulate a stop event with a controlled number of cycles."""

    def __init__(self, wait_results):
        self.wait_results = iter(wait_results)
        self.wait_calls = []

    def wait(self, interval):
        self.wait_calls.append(interval)
        return next(self.wait_results)


class FakeCollector:
    """Simulate SystemCollector and record its method calls."""

    def __init__(self):
        self.calls = []

    def initialize_cpu_measurement(self):
        self.calls.append("initialize_cpu_measurement")

    def collect(self):
        self.calls.append("collect")
        return {"cpu_percent": 25.0, "memory_percent": 50.0}

    def save(self, metrics):
        self.calls.append(("save", metrics))

    def display(self, metrics):
        self.calls.append(("display", metrics))

    def collect_network(self):
        self.calls.append("collect_network")
        return {"bytes_sent": 1000, "bytes_recv": 2000}

    def save_network(self, metrics):
        self.calls.append(("save_network", metrics))

    def display_network(self, metrics):
        self.calls.append(("display_network", metrics))

    def collect_processes(self):
        self.calls.append("collect_processes")
        return [{"pid": 1234, "name": "example"}]

    def save_processes(self, processes):
        self.calls.append(("save_processes", processes))

    def display_processes(self, processes):
        self.calls.append(("display_processes", processes))


class FakeNetworkDiagnostics:
    """Simulate NetworkDiagnostics and record its method calls."""

    def __init__(self):
        self.calls = []

    def run_checks(self):
        self.calls.append("run_checks")
        return [{"check_type": "ping", "success": True}]

    def save(self, results):
        self.calls.append(("save", results))

    def display(self, results):
        self.calls.append(("display", results))


# --------------------------------------------------
#                  Initialization
# --------------------------------------------------


def test_monitoring_task_initializes_and_stops():
    stop_event = FakeStopEvent([True])
    collector = FakeCollector()
    network_diagnostics = FakeNetworkDiagnostics()

    monitoring_task(
        stop_event,
        collector,
        network_diagnostics,
    )

    assert collector.calls == ["initialize_cpu_measurement"]
    assert stop_event.wait_calls == [5]
    assert network_diagnostics.calls == []


# --------------------------------------------------
#                Monitoring cycle
# --------------------------------------------------


def test_monitoring_task_collects_and_saves_metrics(monkeypatch):
    stop_event = FakeStopEvent([False, True])
    collector = FakeCollector()
    network_diagnostics = FakeNetworkDiagnostics()

    monkeypatch.setattr(
        main_module,
        "time",
        SimpleNamespace(monotonic=lambda: 100.0),
    )

    monitoring_task(
        stop_event,
        collector,
        network_diagnostics,
    )

    assert collector.calls.count("initialize_cpu_measurement") == 1
    assert collector.calls.count("collect") == 1
    assert collector.calls.count("collect_network") == 1
    assert collector.calls.count("collect_processes") == 1

    assert (
        "save",
        {"cpu_percent": 25.0, "memory_percent": 50.0},
    ) in collector.calls
    assert (
        "display",
        {"cpu_percent": 25.0, "memory_percent": 50.0},
    ) in collector.calls

    assert (
        "save_network",
        {"bytes_sent": 1000, "bytes_recv": 2000},
    ) in collector.calls
    assert (
        "display_network",
        {"bytes_sent": 1000, "bytes_recv": 2000},
    ) in collector.calls

    assert (
        "save_processes",
        [{"pid": 1234, "name": "example"}],
    ) in collector.calls
    assert (
        "display_processes",
        [{"pid": 1234, "name": "example"}],
    ) in collector.calls

    assert network_diagnostics.calls == [
        "run_checks",
        ("save", [{"check_type": "ping", "success": True}]),
        ("display", [{"check_type": "ping", "success": True}]),
    ]


# --------------------------------------------------
#                 Collection intervals
# --------------------------------------------------


def test_monitoring_task_respects_collection_intervals(monkeypatch):
    stop_event = FakeStopEvent([False, False, True])
    collector = FakeCollector()
    network_diagnostics = FakeNetworkDiagnostics()

    times = iter([100.0, 110.0])

    monkeypatch.setattr(
        main_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(times)),
    )

    monitoring_task(
        stop_event,
        collector,
        network_diagnostics,
        interval=5,
        process_interval=15,
        connectivity_interval=60,
    )

    # System and network metrics are collected on every cycle.
    assert collector.calls.count("collect") == 2
    assert collector.calls.count("collect_network") == 2

    # Process metrics are collected only on the first cycle.
    assert collector.calls.count("collect_processes") == 1

    # Connectivity diagnostics are also collected only once.
    assert network_diagnostics.calls.count("run_checks") == 1

    # The monitoring loop waits once per cycle, including the final stop check.
    assert stop_event.wait_calls == [5, 5, 5]


# --------------------------------------------------
#                    Main function
# --------------------------------------------------


def test_main_starts_and_stops_monitoring(monkeypatch, capsys):
    collector = FakeCollector()
    network_diagnostics = FakeNetworkDiagnostics()

    class FakeEvent:
        def __init__(self):
            self.stop_called = False

        def set(self):
            self.stop_called = True

    class FakeThread:
        def __init__(self, target, args, name):
            self.target = target
            self.args = args
            self.name = name
            self.started = False
            self.join_calls = []

        def start(self):
            self.started = True

        def is_alive(self):
            return False

        def join(self, timeout=None):
            self.join_calls.append(timeout)

    stop_event = FakeEvent()
    thread_instances = []

    def fake_thread_factory(target, args, name):
        thread = FakeThread(target, args, name)
        thread_instances.append(thread)
        return thread

    monkeypatch.setattr(main_module, "SystemCollector", lambda: collector)
    monkeypatch.setattr(
        main_module,
        "NetworkDiagnostics",
        lambda: network_diagnostics,
    )
    monkeypatch.setattr(main_module, "Event", lambda: stop_event)
    monkeypatch.setattr(main_module, "Thread", fake_thread_factory)

    main_module.main()

    thread = thread_instances[0]

    assert thread.target is monitoring_task
    assert thread.args == (stop_event, collector, network_diagnostics)
    assert thread.name == "DiagmoteMonitor"
    assert thread.started is True

    assert stop_event.stop_called is True
    assert thread.join_calls == [None]

    output = capsys.readouterr().out

    assert "Diagmote System Monitor started." in output
    assert "Monitoring stopped." in output


def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    collector = FakeCollector()
    network_diagnostics = FakeNetworkDiagnostics()

    class FakeEvent:
        def __init__(self):
            self.stop_called = False

        def set(self):
            self.stop_called = True

    class FakeThread:
        def __init__(self, target, args, name):
            self.target = target
            self.args = args
            self.name = name
            self.started = False
            self.join_calls = []

        def start(self):
            self.started = True

        def is_alive(self):
            return True

        def join(self, timeout=None):
            self.join_calls.append(timeout)

            if timeout == 1:
                raise KeyboardInterrupt

    stop_event = FakeEvent()
    thread_instances = []

    def fake_thread_factory(target, args, name):
        thread = FakeThread(target, args, name)
        thread_instances.append(thread)
        return thread

    monkeypatch.setattr(main_module, "SystemCollector", lambda: collector)
    monkeypatch.setattr(
        main_module,
        "NetworkDiagnostics",
        lambda: network_diagnostics,
    )
    monkeypatch.setattr(main_module, "Event", lambda: stop_event)
    monkeypatch.setattr(main_module, "Thread", fake_thread_factory)

    main_module.main()

    thread = thread_instances[0]

    assert thread.started is True
    assert stop_event.stop_called is True
    assert thread.join_calls == [1, None]

    output = capsys.readouterr().out

    assert "Stopping Diagmote..." in output
    assert "Monitoring stopped." in output
