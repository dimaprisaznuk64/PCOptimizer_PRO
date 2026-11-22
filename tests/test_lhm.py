from __future__ import annotations

from app.sensors.lhm_backend import LhmReader, pick_temperatures
from app.sensors.temperature_names import KIND_BOARD, KIND_CPU, KIND_GPU, temperature_kind


class _Sensor:
    def __init__(self, name: str, value: float, sensor_type: object = "Temperature") -> None:
        self.Name = name
        self.Value = value
        self.SensorType = sensor_type


class _Hardware:
    def __init__(self, sensors: tuple[_Sensor, ...] = (), sub: tuple[object, ...] = ()) -> None:
        self.Sensors = sensors
        self.SubHardware = sub
        self.updates = 0

    def Update(self) -> None:
        self.updates += 1


class _Computer:
    def __init__(self, hardware: tuple[_Hardware, ...]) -> None:
        self.Hardware = hardware
        self.opened = 0
        self.closed = 0

    def Open(self) -> None:
        self.opened += 1

    def Close(self) -> None:
        self.closed += 1


class _StaticReader:
    last_error = ""

    def __init__(self, values: dict[str, tuple[float, str]] | None) -> None:
        self.values = values
        self.closed = False

    def read(self) -> dict[str, tuple[float, str]] | None:
        return self.values

    def close(self) -> None:
        self.closed = True


def test_pick_temperatures_prefers_named_sensors() -> None:
    result = pick_temperatures(
        [
            ("Tctl/Tdie", 71.0),
            ("Core 0", 68.0),
            ("System", 44.0),
            ("CPU Socket", 46.0),
            ("GPU Core", 61.0),
            ("Fan", 0.0),
        ]
    )
    assert result[KIND_CPU] == (71.0, "Tctl/Tdie")
    assert result[KIND_BOARD] == (44.0, "System")
    assert result[KIND_GPU] == (61.0, "GPU Core")


def test_cpu_socket_is_a_board_sensor() -> None:
    assert temperature_kind("CPU Socket") == KIND_BOARD


def test_reader_walks_subhardware_and_opens_once(tmp_path) -> None:
    board = _Hardware((_Sensor("System", 44.0),))
    cpu = _Hardware(
        (_Sensor("Tctl/Tdie", 71.0), _Sensor("Fan", 900, "Fan")),
        (board,),
    )
    computer = _Computer((cpu,))
    refs: list[str] = []
    reader = LhmReader(
        tmp_path,
        add_reference=refs.append,
        computer_factory=lambda: computer,
    )

    first = reader.read()
    second = reader.read()
    reader.close()

    assert first == {
        KIND_CPU: (71.0, "Tctl/Tdie"),
        KIND_BOARD: (44.0, "System"),
    }
    assert second == first
    assert computer.opened == 1
    assert cpu.updates == 2
    assert computer.closed == 1
    assert len(refs) == 9


def test_reader_ignores_zero_temperature(tmp_path) -> None:
    computer = _Computer((_Hardware((_Sensor("Core (Tctl/Tdie)", 0.0),)),))
    reader = LhmReader(tmp_path, add_reference=lambda _path: None, computer_factory=lambda: computer)
    assert reader.read() is None


def test_reader_reports_errors(tmp_path) -> None:
    def _fail() -> object:
        raise RuntimeError("administrator required")

    reader = LhmReader(tmp_path, add_reference=lambda _path: None, computer_factory=_fail)
    assert reader.read() is None
    assert "administrator required" in reader.last_error


def test_thermal_backend_uses_pythonnet_reader() -> None:
    from app.sensors.thermal_backend import ThermalBackend

    backend = ThermalBackend(_StaticReader({KIND_CPU: (71.0, "cpu"), KIND_BOARD: (44.0, "board")}))
    try:
        part = backend.collect()
        assert part is not None
        thermal = part["thermal"]
        assert thermal.source == "lhm_pythonnet"
        assert thermal.temperatures == ((KIND_BOARD, 44.0), (KIND_CPU, 71.0))
    finally:
        backend.close()


def test_thermal_backend_closes_reader() -> None:
    from app.sensors.thermal_backend import ThermalBackend

    reader = _StaticReader(None)
    backend = ThermalBackend(reader)
    backend.close()
    assert reader.closed is True
