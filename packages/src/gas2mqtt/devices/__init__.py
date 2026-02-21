"""Device handlers for gas2mqtt.

Contains cosalette device implementations:
- gas_counter: @app.device — stateful trigger detection + counter
- temperature: @app.telemetry — periodic temperature reporting
- magnetometer: @app.telemetry — debug raw magnetometer output (optional)
"""

from __future__ import annotations

from gas2mqtt.devices.gas_counter import gas_counter

__all__ = ["gas_counter"]
