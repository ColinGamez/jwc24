"""Project one explicit dated JMA observation into native measurement integers.

This is a replacement conversion policy, not an original Weathernews algorithm.
No native location/clock, condition, forecast, receipt acceptance or publication
is created here. All original source values and dates remain in the result.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math

from jwc24.jma_weather import (
    JMAError, ObservationRecord, ObservationSource, ObservationValue,
    SourceReceipt, Station,
)


POLICY_ID = "jwc24-jma-measurements-v1"
ROUNDING = "nearest_half_away_from_zero"
MISSING_TEMPERATURE = -128
MISSING_WIND = 255


@dataclass(frozen=True)
class NativeObservationMeasurements:
    station: Station
    source_record: ObservationRecord
    source_receipt: SourceReceipt
    policy_id: str
    rounding: str
    temperature_celsius: int
    temperature_fahrenheit: int
    wind_direction: int
    wind_speed_metric: int
    wind_speed_imperial: int
    unavailable_reasons: tuple[str, ...]


def _number(value: object) -> Fraction:
    # Bound before string/Fraction conversion, including caller-constructed data.
    if type(value) not in (int, float) or not -1_000_000 <= value <= 1_000_000:
        raise JMAError("measurement is not a bounded finite number")
    if type(value) is float and not math.isfinite(value):
        raise JMAError("measurement is not a bounded finite number")
    return Fraction(str(value))


def _rounded(value: Fraction, minimum: int, maximum: int) -> int:
    # Exact rational arithmetic; independent of float ties or Decimal context.
    magnitude = abs(value)
    integer = (2 * magnitude.numerator + magnitude.denominator) // (2 * magnitude.denominator)
    result = -integer if value < 0 else integer
    if not minimum <= result <= maximum:
        raise JMAError("rounded measurement exceeds its native range")
    return result


def _eligible(value: ObservationValue | None, name: str, unit: str,
              period: int | None, reasons: list[str]) -> bool:
    if value is None:
        reasons.append(name + ":absent")
        return False
    if (type(value) is not ObservationValue or value.name != name
            or type(value.qc) is not int or not 0 <= value.qc <= 7
            or value.unit != unit or value.period_seconds != period
            or value.supported_unit is not True):
        raise JMAError("measurement contract differs from the reviewed JMA field")
    if value.raw_value is None:
        reasons.append(name + ":missing")
        return False
    _number(value.raw_value)
    if value.qc != 0:
        reasons.append(name + ":qualified")
        return False
    return True


def project_observation(source: ObservationSource, record_key_jst: str, *,
                        rounding: str) -> NativeObservationMeasurements:
    """Use only explicit QC-0 fields from one selected source record.

    The caller must choose the record and rounding policy. This never chooses a
    nearest station, newest record or acceptable age. JMA's fractional values
    are converted before rounding each independent native unit. QC 1 is normal
    in JMA's own client but qualified; this local policy keeps it unavailable.
    """
    if rounding != ROUNDING or type(rounding) is not str:
        raise JMAError("explicit supported measurement rounding policy required")
    if type(source) is not ObservationSource or type(record_key_jst) is not str:
        raise JMAError("explicit typed source and observation key required")
    selected = [r for r in source.records if r.source_time_key_jst == record_key_jst]
    if len(selected) != 1:
        raise JMAError("selected observation key is absent or ambiguous")
    record = selected[0]
    if any(type(v) is not ObservationValue for v in record.values):
        raise JMAError("typed observation measurements required")
    names = [v.name for v in record.values]
    if len(names) != len(set(names)):
        raise JMAError("observation has duplicate measurement fields")
    reasons: list[str] = []
    temperature = record.value("temp")
    celsius = fahrenheit = MISSING_TEMPERATURE
    if _eligible(temperature, "temp", "degC", None, reasons):
        raw_celsius = _number(temperature.raw_value)
        celsius = _rounded(raw_celsius, -127, 127)
        fahrenheit = _rounded(raw_celsius * Fraction(9, 5) + 32, -127, 127)

    speed, direction = record.value("wind"), record.value("windDirection")
    speed_ok = _eligible(speed, "wind", "m/s", 600, reasons)
    direction_ok = _eligible(direction, "windDirection", "JMA_16_direction_0_calm", 600, reasons)
    native_direction = metric = imperial = MISSING_WIND
    if speed_ok and _number(speed.raw_value) < 0:
        raise JMAError("wind speed cannot be negative")
    if direction_ok and (type(direction.raw_value) is not int or not 0 <= direction.raw_value <= 16):
        raise JMAError("wind direction is outside the reviewed JMA enum")
    if speed_ok and direction_ok:
        raw_speed = _number(speed.raw_value)
        # Exact definitions: 1 km = 1000 m, 1 international mile = 1609.344 m.
        metric = _rounded(raw_speed * Fraction(18, 5), 0, 254)
        imperial = _rounded(raw_speed * Fraction(3125, 1397), 0, 254)
        native_direction = direction.raw_value
    else:
        # FF direction suppresses this native caller before either speed read.
        # In particular, do not emit calm(0) paired with missing speed(FF).
        reasons.append("wind:incomplete_pair_suppressed")
    return NativeObservationMeasurements(
        source.station, record, source.receipt, POLICY_ID, ROUNDING,
        celsius, fahrenheit, native_direction, metric, imperial, tuple(reasons),
    )
