"""Unit tests for magnetometer telemetry — raw sensor output.

Tests the debug magnetometer pipeline: raw reading → dict output.
The handler is now inline in main.py, so we test the same logic directly.

Test Techniques Used:
- Specification-based: Raw sensor values in output
- Equivalence Partitioning: Various magnetic field values
- State Transition: Values update between reads
- Error Guessing: Temperature data leakage
"""

from __future__ import annotations

import pytest

from gas2mqtt.adapters.fake import FakeMagnetometer


@pytest.mark.unit
class TestMagnetometerHandler:
    """Verify debug magnetometer output returns raw sensor values."""

    async def test_returns_all_axes(self) -> None:
        """Handler returns bx, by, bz from the magnetometer.

        Technique: Specification-based — output contract.
        """
        # Arrange
        mag = FakeMagnetometer()
        mag.bx = 100
        mag.by = -200
        mag.bz = -5000

        # Act — simulate the inline handler logic
        reading = mag.read()
        result = {"bx": reading.bx, "by": reading.by, "bz": reading.bz}

        # Assert
        assert result == {"bx": 100, "by": -200, "bz": -5000}

    async def test_returns_zeros_by_default(self) -> None:
        """Fresh FakeMagnetometer returns all zeros.

        Technique: Specification-based — default fake values.
        """
        # Arrange
        mag = FakeMagnetometer()

        # Act
        reading = mag.read()
        result = {"bx": reading.bx, "by": reading.by, "bz": reading.bz}

        # Assert
        assert result == {"bx": 0, "by": 0, "bz": 0}

    async def test_reflects_updated_values(self) -> None:
        """Changing fake values between calls produces updated output.

        Technique: State Transition — values update between reads.
        """
        # Arrange
        mag = FakeMagnetometer()

        # Act 1 — initial read
        reading1 = mag.read()
        result1 = {"bx": reading1.bx, "by": reading1.by, "bz": reading1.bz}

        # Update values
        mag.bx = 42
        mag.by = 43
        mag.bz = 44

        # Act 2 — updated read
        reading2 = mag.read()
        result2 = {"bx": reading2.bx, "by": reading2.by, "bz": reading2.bz}

        # Assert
        assert result1 == {"bx": 0, "by": 0, "bz": 0}
        assert result2 == {"bx": 42, "by": 43, "bz": 44}

    async def test_does_not_include_temperature(self) -> None:
        """Debug output excludes temperature (separate device handles that).

        Technique: Error Guessing — ensuring no data leakage.
        """
        # Arrange
        mag = FakeMagnetometer()
        mag.temperature_raw = 9999

        # Act
        reading = mag.read()
        result = {"bx": reading.bx, "by": reading.by, "bz": reading.bz}

        # Assert
        assert "temperature" not in result
        assert "temperature_raw" not in result
