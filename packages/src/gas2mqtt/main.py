"""gas2mqtt application entry point.

Wires the cosalette App with all devices, adapters, and settings.
The module-level ``app`` object is the entry point for the CLI:
``gas2mqtt`` runs ``app.run()``.
"""

from __future__ import annotations

import cosalette
from cosalette import OnChange, Pt1Filter

from gas2mqtt import __version__
from gas2mqtt.adapters.fake import FakeMagnetometer, NullStorage
from gas2mqtt.adapters.json_storage import JsonFileStorage
from gas2mqtt.adapters.qmc5883l import Qmc5883lAdapter
from gas2mqtt.devices.gas_counter import gas_counter
from gas2mqtt.ports import MagnetometerPort, StateStoragePort
from gas2mqtt.settings import Gas2MqttSettings


def _make_storage_adapter(
    settings: Gas2MqttSettings,
) -> JsonFileStorage | NullStorage:
    """Create the appropriate storage adapter based on settings.

    Returns :class:`NullStorage` when ``state_file`` is ``None``
    (persistence disabled), otherwise :class:`JsonFileStorage`
    pointing at the configured path.
    """
    if settings.state_file is None:
        return NullStorage()
    return JsonFileStorage(settings.state_file)


# --- App creation ---

app = cosalette.App(
    name="gas2mqtt",
    version=__version__,
    description="Domestic gas meter reader via QMC5883L magnetometer",
    settings_class=Gas2MqttSettings,
)
"""Module-level app instance — entry point for the CLI."""

settings: Gas2MqttSettings = app.settings  # type: ignore[assignment]

# --- Adapter registration ---

app.adapter(MagnetometerPort, Qmc5883lAdapter, dry_run=FakeMagnetometer)
app.adapter(StateStoragePort, _make_storage_adapter, dry_run=NullStorage)

# --- Device registration ---

app.add_device("gas_counter", gas_counter)


def _make_pt1(settings: Gas2MqttSettings) -> Pt1Filter:
    """Create PT1 filter from settings for temperature smoothing."""
    return Pt1Filter(tau=settings.smoothing_tau, dt=settings.temperature_interval)


@app.telemetry(
    "temperature",
    interval=settings.temperature_interval,
    publish=OnChange(threshold={"temperature": 0.05}),
    init=_make_pt1,
)
async def _temperature(
    magnetometer: MagnetometerPort,
    settings: Gas2MqttSettings,
    pt1: Pt1Filter,
) -> dict[str, object]:
    reading = magnetometer.read()
    raw_celsius = settings.temp_scale * reading.temperature_raw + settings.temp_offset
    return {"temperature": round(pt1.update(raw_celsius), 1)}


@app.telemetry(
    "magnetometer",
    interval=settings.poll_interval,
    enabled=settings.enable_debug_device,
)
async def _magnetometer(
    magnetometer: MagnetometerPort,
) -> dict[str, object]:
    reading = magnetometer.read()
    return {"bx": reading.bx, "by": reading.by, "bz": reading.bz}
