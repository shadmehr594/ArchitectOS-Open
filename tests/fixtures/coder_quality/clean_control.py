"""Clean control for the Tier 1 static quality gate.

Deliberately contains none of the patterns the gate flags: no eval/exec, no
mutable default arguments, no swallowed exceptions, no rounding, no shell.
It must produce an empty finding list — this is the false-positive guard.
"""


def celsius_to_fahrenheit(celsius):
    """Convert a Celsius temperature to Fahrenheit."""
    if not isinstance(celsius, (int, float)):
        raise TypeError("celsius must be a number")
    return celsius * 9 / 5 + 32


def fahrenheit_to_celsius(fahrenheit):
    """Convert a Fahrenheit temperature to Celsius."""
    if not isinstance(fahrenheit, (int, float)):
        raise TypeError("fahrenheit must be a number")
    return (fahrenheit - 32) * 5 / 9


def format_temperature(value, unit):
    """Format a temperature with one decimal place and a unit suffix."""
    if unit not in ("C", "F"):
        raise ValueError("unit must be 'C' or 'F'")
    return "%.1f%s" % (value, unit)


def classify_temperature(celsius):
    """Return a coarse band name for a Celsius reading."""
    if celsius <= 0:
        return "freezing"
    if celsius < 18:
        return "cold"
    if celsius < 26:
        return "mild"
    return "warm"
