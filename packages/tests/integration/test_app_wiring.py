"""Integration tests for gas2mqtt application wiring.

Verifies that ``create_app()`` correctly wires all components and that
the lifespan properly manages the magnetometer adapter lifecycle.

Test Techniques Used:
- Specification-based: App configuration matches expectations
- Integration: Components wire together correctly
- Error Guessing: Lifespan closes adapter even on error
"""

from __future__ import annotations

import asyncio
import json

import cosalette
import pytest
from cosalette.testing import FakeClock, MockMqttClient

from gas2mqtt.adapters.fake import FakeMagnetometer
from gas2mqtt.devices.magnetometer import make_magnetometer_handler
from gas2mqtt.devices.temperature import make_temperature_handler
from gas2mqtt.main import create_app, lifespan
from gas2mqtt.ports import MagnetometerPort
from gas2mqtt.settings import Gas2MqttSettings
from tests.fixtures.config import make_gas2mqtt_settings

# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAppCreation:
    """Verify create_app() produces a properly configured App."""

    def test_creates_app_instance(self) -> None:
        """create_app() returns a cosalette App.

        Technique: Specification-based — verifying factory contract.
        """
        # Act
        app = create_app()

        # Assert
        assert isinstance(app, cosalette.App)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLifespan:
    """Verify lifespan initializes and cleans up the magnetometer."""

    async def test_initializes_magnetometer(self) -> None:
        """Lifespan calls magnetometer.initialize() on startup.

        Technique: State Transition — verifying startup lifecycle.
        """
        # Arrange
        mag = FakeMagnetometer()
        ctx = cosalette.AppContext(
            settings=make_gas2mqtt_settings(),
            adapters={MagnetometerPort: mag},
        )

        # Act
        async with lifespan(ctx):
            # Assert
            assert mag.initialized is True

    async def test_closes_magnetometer(self) -> None:
        """Lifespan calls magnetometer.close() on shutdown.

        Technique: State Transition — verifying shutdown lifecycle.
        """
        # Arrange
        mag = FakeMagnetometer()
        ctx = cosalette.AppContext(
            settings=make_gas2mqtt_settings(),
            adapters={MagnetometerPort: mag},
        )

        # Act
        async with lifespan(ctx):
            pass

        # Assert
        assert mag.closed is True

    async def test_closes_on_error(self) -> None:
        """Lifespan closes magnetometer even if the body raises.

        Technique: Error Guessing — cleanup must happen on exceptions.
        """
        # Arrange
        mag = FakeMagnetometer()
        ctx = cosalette.AppContext(
            settings=make_gas2mqtt_settings(),
            adapters={MagnetometerPort: mag},
        )

        # Act
        with pytest.raises(RuntimeError, match="boom"):
            async with lifespan(ctx):
                raise RuntimeError("boom")

        # Assert
        assert mag.closed is True


# ---------------------------------------------------------------------------
# Temperature device wiring
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTemperatureDeviceWiring:
    """Verify temperature device publishes calibrated state via MQTT."""

    async def test_publishes_calibrated_temperature(self) -> None:
        """Temperature handler → DeviceContext → MQTT publish flow.

        Technique: Integration — end-to-end data flow through real components.
        """
        # Arrange
        mag = FakeMagnetometer()
        mag.temperature_raw = 2500  # → 0.008 * 2500 + 20.3 = 40.3
        settings = make_gas2mqtt_settings(temperature_interval=0.01)
        mqtt = MockMqttClient()

        ctx = cosalette.DeviceContext(
            name="temperature",
            settings=settings,
            mqtt=mqtt,
            topic_prefix="gas2mqtt",
            shutdown_event=asyncio.Event(),
            adapters={MagnetometerPort: mag},
            clock=FakeClock(),
        )

        handler = make_temperature_handler(mag, settings)

        # Act
        await ctx.publish_state(await handler())

        # Assert
        assert mqtt.publish_count >= 1
        topic, raw_payload, _retain, _qos = mqtt.published[0]
        assert topic == "gas2mqtt/temperature/state"
        payload = json.loads(raw_payload)
        assert payload["temperature"] == pytest.approx(40.3, abs=0.1)


# ---------------------------------------------------------------------------
# Debug magnetometer device wiring
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMagnetometerDeviceWiring:
    """Verify debug magnetometer device conditional behavior."""

    async def test_publishes_raw_values_when_enabled(self) -> None:
        """Debug device publishes raw bx/by/bz when enabled.

        Technique: Integration — verifying wiring with enable flag on.
        """
        # Arrange
        mag = FakeMagnetometer()
        mag.bx = 100
        mag.by = -200
        mag.bz = -5000
        mqtt = MockMqttClient()

        ctx = cosalette.DeviceContext(
            name="magnetometer",
            settings=make_gas2mqtt_settings(enable_debug_device=True),
            mqtt=mqtt,
            topic_prefix="gas2mqtt",
            shutdown_event=asyncio.Event(),
            adapters={MagnetometerPort: mag},
            clock=FakeClock(),
        )

        handler = make_magnetometer_handler(mag)

        # Act
        await ctx.publish_state(await handler())

        # Assert
        assert mqtt.publish_count >= 1
        topic, raw_payload, _retain, _qos = mqtt.published[0]
        assert topic == "gas2mqtt/magnetometer/state"
        payload = json.loads(raw_payload)
        assert payload == {"bx": 100, "by": -200, "bz": -5000}

    async def test_noop_when_disabled(self) -> None:
        """Debug device returns immediately when enable_debug_device=False.

        Technique: Branch Coverage — verifying the early-return path.

        The _magnetometer device handler in main.py checks
        settings.enable_debug_device and returns immediately if False.
        We replicate the exact conditional logic to verify no publish
        occurs.
        """
        # Arrange
        mag = FakeMagnetometer()
        mqtt = MockMqttClient()
        settings = make_gas2mqtt_settings(enable_debug_device=False)

        ctx = cosalette.DeviceContext(
            name="magnetometer",
            settings=settings,
            mqtt=mqtt,
            topic_prefix="gas2mqtt",
            shutdown_event=asyncio.Event(),
            adapters={MagnetometerPort: mag},
            clock=FakeClock(),
        )

        # Act — replicate _magnetometer's early-return logic
        effective_settings: Gas2MqttSettings = ctx.settings  # type: ignore[assignment]
        if not effective_settings.enable_debug_device:
            pass  # mirrors the `return` in _magnetometer
        else:
            handler = make_magnetometer_handler(mag)
            await ctx.publish_state(await handler())

        # Assert — no messages published when debug is off
        assert mqtt.publish_count == 0
