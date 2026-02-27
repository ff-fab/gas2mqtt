"""Integration tests for gas2mqtt application wiring.

Verifies that module-level declarations in ``main.py`` correctly wire
all components, that adapter lifecycle methods (__aenter__/__aexit__)
properly manage the magnetometer, and that device registration uses
eager settings with ``enabled=`` for conditional registration.

Test Techniques Used:
- Specification-based: App configuration matches expectations
- Integration: Handler factories exercised end-to-end with real domain objects
- State Transition: Adapter __aenter__/__aexit__ lifecycle
- Branch Coverage: Magnetometer conditional registration via enabled=
- Error Guessing: __aexit__ closes adapter even on error
"""

from __future__ import annotations

from pathlib import Path

import cosalette
import pytest

from gas2mqtt.adapters.fake import FakeMagnetometer, NullStorage
from gas2mqtt.adapters.json_storage import JsonFileStorage
from gas2mqtt.main import _make_storage_adapter, app
from gas2mqtt.ports import StateStoragePort
from tests.fixtures.config import make_gas2mqtt_settings

# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAppCreation:
    """Verify module-level app is a properly configured App."""

    def test_creates_app_instance(self) -> None:
        """Module-level app is a cosalette App.

        Technique: Specification-based — verifying module-level wiring.
        """
        # Assert
        assert isinstance(app, cosalette.App)


# ---------------------------------------------------------------------------
# Adapter lifecycle (__aenter__ / __aexit__)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdapterLifecycle:
    """Verify adapter __aenter__/__aexit__ manages magnetometer lifecycle."""

    async def test_aenter_initializes_magnetometer(self) -> None:
        """__aenter__ calls initialize() on the adapter.

        Technique: State Transition — verifying startup lifecycle.
        """
        # Arrange
        mag = FakeMagnetometer()

        # Act
        async with mag:
            # Assert
            assert mag.initialized is True

    async def test_aexit_closes_magnetometer(self) -> None:
        """__aexit__ calls close() on the adapter.

        Technique: State Transition — verifying shutdown lifecycle.
        """
        # Arrange
        mag = FakeMagnetometer()

        # Act
        async with mag:
            pass

        # Assert
        assert mag.closed is True

    async def test_aexit_closes_on_error(self) -> None:
        """__aexit__ closes adapter even if the body raises.

        Technique: Error Guessing — cleanup must happen on exceptions.
        """
        # Arrange
        mag = FakeMagnetometer()

        # Act
        with pytest.raises(RuntimeError, match="boom"):
            async with mag:
                raise RuntimeError("boom")

        # Assert
        assert mag.closed is True


# ---------------------------------------------------------------------------
# Temperature registration
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTemperatureRegistration:
    """Verify temperature is registered as telemetry with PT1 filter."""

    def test_temperature_registered_as_telemetry(self) -> None:
        """Module-level app registers temperature as a telemetry device.

        Technique: Specification-based — verifying registration contract.
        """
        # Assert
        telemetry_names = [t.name for t in app._telemetry]  # noqa: SLF001
        assert "temperature" in telemetry_names


# ---------------------------------------------------------------------------
# Debug magnetometer registration (enabled= parameter)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMagnetometerRegistration:
    """Verify magnetometer conditional registration via enabled= parameter.

    The module-level app uses ``enabled=settings.enable_debug_device``
    on the ``@app.telemetry("magnetometer", ...)`` decorator. Since the
    default settings have ``enable_debug_device=False``, the magnetometer
    is NOT registered in the singleton app.

    The ``_magnetometer`` handler function is still defined at module level,
    so we can test it directly to verify correctness independent of wiring.
    """

    def test_noop_when_disabled_by_default(self) -> None:
        """Default settings disable magnetometer registration.

        Technique: Branch Coverage — verifying enabled=False path.
        Default ``enable_debug_device`` is False, so the magnetometer
        telemetry is skipped during module-level registration.
        """
        # Assert
        telemetry_names = [t.name for t in app._telemetry]  # noqa: SLF001
        assert "magnetometer" not in telemetry_names

    async def test_magnetometer_handler_returns_readings(self) -> None:
        """_magnetometer handler returns correct reading dict.

        Technique: Integration — exercise the handler directly with a
        fake magnetometer to verify it works regardless of enabled= wiring.
        """
        # Arrange
        from gas2mqtt.main import _magnetometer

        mag = FakeMagnetometer()
        async with mag:
            # Act
            result = await _magnetometer(mag)

        # Assert
        assert "bx" in result
        assert "by" in result
        assert "bz" in result


# ---------------------------------------------------------------------------
# Storage adapter wiring
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestStorageAdapterWiring:
    """Verify StateStoragePort adapter registration.

    Technique: Specification-based — adapter factory produces correct type
    depending on the ``state_file`` setting.
    """

    def test_storage_adapter_returns_null_when_no_state_file(self) -> None:
        """Factory returns NullStorage when state_file is None (default)."""
        # Arrange
        settings = make_gas2mqtt_settings(state_file=None)

        # Act
        storage = _make_storage_adapter(settings)

        # Assert
        assert isinstance(storage, NullStorage)

    def test_storage_adapter_returns_json_file_when_configured(
        self,
        tmp_path: Path,
    ) -> None:
        """Factory returns JsonFileStorage when state_file is set."""
        # Arrange
        state_path = tmp_path / "state.json"
        settings = make_gas2mqtt_settings(state_file=state_path)

        # Act
        storage = _make_storage_adapter(settings)

        # Assert
        assert isinstance(storage, JsonFileStorage)

    def test_storage_port_registered_in_app(self) -> None:
        """Module-level app registers StateStoragePort in the adapter registry."""
        # Assert
        assert StateStoragePort in app._adapters  # noqa: SLF001
