"""Drivetrain identifiers.

The Tax Authority `drive_code` follows the rules-file mapping (0=petrol, 1=hybrid, 2=plug-in,
3=electric), NOT the CSV header text. See raw/README.md.
"""

from typing import Literal

Drive = Literal["petrol", "hybrid", "plugin", "electric"]

DRIVE_BY_CODE: dict[int, Drive] = {
    0: "petrol",
    1: "hybrid",
    2: "plugin",
    3: "electric",
}
