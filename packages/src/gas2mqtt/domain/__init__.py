"""Pure domain logic for gas2mqtt.

Contains stateless/stateful domain objects with no I/O dependencies:
- SchmittTrigger: Detects gas meter rotations from magnetic field
- EwmaFilter: Exponentially weighted moving average for temperature
- ConsumptionTracker: Tracks gas consumption in m³
"""
