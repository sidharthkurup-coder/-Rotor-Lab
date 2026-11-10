"""Domain models and strict input validation for RotorLab propulsion analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DataProvenance(str, Enum):
    """Explicit classification of propulsion performance data provenance.

    Never fabricate manufacturer specifications or misrepresent synthetic estimates.
    """

    MANUFACTURER_DATASHEET = "Manufacturer Measurements"
    USER_MEASURED = "User-Supplied Measurements"
    ILLUSTRATIVE_SYNTHETIC = "Illustrative Synthetic Data"
    CALCULATED_ESTIMATE = "Calculated Estimate"


class SeverityLevel(str, Enum):
    """Engineering compatibility finding severity levels."""

    PASS = "PASS"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class MotorSpec:
    """Brushless DC (BLDC) motor engineering specification."""

    manufacturer: str
    model: str
    kv_rating: float  # RPM/V
    max_continuous_current_a: float  # Amperes (e.g., 180s continuous limit)
    max_continuous_power_w: float  # Watts
    internal_resistance_mohm: float = 100.0  # milliohms
    no_load_current_a: float = 0.5  # Amperes
    min_cells_s: int = 3
    max_cells_s: int = 6
    mass_g: float = 100.0  # grams

    def __post_init__(self) -> None:
        if not self.manufacturer or not self.manufacturer.strip():
            raise ValueError("Motor manufacturer must not be empty.")
        if not self.model or not self.model.strip():
            raise ValueError("Motor model must not be empty.")
        if self.kv_rating <= 0:
            raise ValueError("Motor KV rating must be strictly positive.")
        if self.max_continuous_current_a <= 0:
            raise ValueError("Motor max continuous current must be strictly positive.")
        if self.max_continuous_power_w <= 0:
            raise ValueError("Motor max continuous power must be strictly positive.")
        if self.internal_resistance_mohm < 0:
            raise ValueError("Motor internal resistance cannot be negative.")
        if self.no_load_current_a < 0:
            raise ValueError("Motor no-load current cannot be negative.")
        if self.min_cells_s < 1 or self.max_cells_s < self.min_cells_s:
            raise ValueError("Invalid LiPo cell rating range (min_cells_s, max_cells_s).")
        if self.mass_g <= 0:
            raise ValueError("Motor mass must be strictly positive.")

    @property
    def full_name(self) -> str:
        return f"{self.manufacturer} {self.model} (KV{int(round(self.kv_rating))})"


@dataclass(frozen=True)
class PropellerSpec:
    """Multirotor propeller geometry and specification."""

    manufacturer: str
    model: str
    diameter_in: float  # inches
    pitch_in: float  # inches
    num_blades: int = 2
    material: str = "Carbon Fiber (CF)"
    mass_g: float = 18.0  # grams

    def __post_init__(self) -> None:
        if not self.model or not self.model.strip():
            raise ValueError("Propeller model must not be empty.")
        if self.diameter_in <= 0:
            raise ValueError("Propeller diameter must be strictly positive.")
        if self.pitch_in <= 0:
            raise ValueError("Propeller pitch must be strictly positive.")
        if self.num_blades < 1 or self.num_blades > 8:
            raise ValueError("Number of propeller blades must be between 1 and 8.")
        if self.mass_g < 0:
            raise ValueError("Propeller mass cannot be negative.")

    @property
    def code(self) -> str:
        return f"{self.diameter_in:g}x{self.pitch_in:g}"


@dataclass(frozen=True)
class ESCSpec:
    """Electronic Speed Controller (ESC) specification."""

    name: str
    continuous_current_a: float  # Amperes
    peak_current_a: float  # Amperes (burst 10s)
    min_cells_s: int = 3
    max_cells_s: int = 6
    mass_g: float = 25.0  # grams

    def __post_init__(self) -> None:
        if self.continuous_current_a <= 0:
            raise ValueError("ESC continuous current rating must be strictly positive.")
        if self.peak_current_a < self.continuous_current_a:
            raise ValueError("ESC peak current rating must be >= continuous current rating.")
        if self.min_cells_s < 1 or self.max_cells_s < self.min_cells_s:
            raise ValueError("Invalid ESC LiPo cell rating range.")
        if self.mass_g < 0:
            raise ValueError("ESC mass cannot be negative.")


@dataclass(frozen=True)
class BatterySpec:
    """Lithium-Polymer / Lithium-Ion UAV flight battery specification."""

    name: str
    cell_count_s: int  # Series cell count
    nominal_voltage_v: float  # Volts (e.g., 14.8V for 4S, 22.2V for 6S)
    operating_voltage_v: float  # Volts (operating voltage under analysis)
    capacity_mah: float  # milliampere-hours
    continuous_c_rating: float  # C-rate (1/h)
    burst_c_rating: float = 50.0  # C-rate (1/h)
    usable_capacity_fraction: float = 0.80  # Default 80% DoD (20% reserve)
    internal_resistance_per_cell_mohm: float = 4.0  # mOhm per cell
    mass_g: float = 550.0  # grams

    def __post_init__(self) -> None:
        if self.cell_count_s < 1 or self.cell_count_s > 24:
            raise ValueError("Battery cell count must be between 1S and 24S.")
        if self.nominal_voltage_v <= 0:
            raise ValueError("Battery nominal voltage must be strictly positive.")
        if self.operating_voltage_v <= 0:
            raise ValueError("Operating voltage must be strictly positive.")
        if self.capacity_mah <= 0:
            raise ValueError("Battery capacity must be strictly positive.")
        if self.continuous_c_rating <= 0:
            raise ValueError("Battery continuous C-rating must be strictly positive.")
        if self.burst_c_rating < self.continuous_c_rating:
            raise ValueError("Battery burst C-rating must be >= continuous C-rating.")
        if not (0.10 <= self.usable_capacity_fraction <= 1.0):
            raise ValueError("Usable capacity fraction must be between 0.10 (10%) and 1.00 (100%).")
        if self.internal_resistance_per_cell_mohm < 0:
            raise ValueError("Battery internal resistance cannot be negative.")
        if self.mass_g < 0:
            raise ValueError("Battery mass cannot be negative.")

    @property
    def reserve_fraction(self) -> float:
        return round(1.0 - self.usable_capacity_fraction, 4)


@dataclass(frozen=True)
class AirframeSpec:
    """Multirotor airframe, mass budget, and operating mission profile."""

    frame_type: str  # e.g., "Quadcopter (X4)", "Hexacopter (X6)", "Octocopter (X8)"
    num_motors: int
    aircraft_dry_mass_kg: float  # Airframe mass including propulsion & battery (without payload) [kg]
    payload_mass_kg: float  # Mission payload mass [kg]
    avionics_power_w: float = 8.0  # Flight controller, GNSS, telemetry, companion computer [W]
    operating_throttle_pct: float = 65.0  # Target representative flight/cruise throttle [%]
    altitude_m: float = 0.0  # Geopotential altitude above MSL [m]
    temp_offset_c: float = 0.0  # ISA temperature deviation [deg C]

    def __post_init__(self) -> None:
        if self.num_motors < 1 or self.num_motors > 32:
            raise ValueError("Number of motors must be between 1 and 32.")
        if self.aircraft_dry_mass_kg <= 0:
            raise ValueError("Aircraft mass must be strictly positive.")
        if self.payload_mass_kg < 0:
            raise ValueError("Payload mass cannot be negative.")
        if self.avionics_power_w < 0:
            raise ValueError("Avionics auxiliary power cannot be negative.")
        if not (0.0 <= self.operating_throttle_pct <= 100.0):
            raise ValueError("Operating throttle percentage must be between 0% and 100%.")

    @property
    def total_mass_kg(self) -> float:
        return self.aircraft_dry_mass_kg + self.payload_mass_kg


@dataclass(frozen=True)
class EngineeringMargins:
    """Configurable engineering thresholds for propulsion compatibility & margin evaluation."""

    esc_current_safety_factor: float = 1.20  # ESC continuous current >= 1.20 * motor peak current
    motor_current_margin_ratio: float = 0.90  # Warn if operating current > 90% of motor max limit
    battery_c_margin_ratio: float = 0.85  # Warn if continuous current > 85% of battery max continuous A
    voltage_mismatch_tolerance_pct: float = 10.0  # Warn if operating V differs from dataset test V by >10%
    min_hover_twr: float = 1.50  # Minimum TWR for basic controlled hover margin
    recommended_agile_twr: float = 2.00  # Standard multirotor engineering design target (TWR >= 2.0)
    max_hover_throttle_pct: float = 65.0  # Warn if hover equilibrium requires >65% throttle

    def __post_init__(self) -> None:
        if self.esc_current_safety_factor < 1.0:
            raise ValueError("ESC current safety factor must be >= 1.0.")
        if not (0.50 <= self.motor_current_margin_ratio <= 1.0):
            raise ValueError("Motor current margin ratio must be between 0.50 and 1.0.")
        if not (0.50 <= self.battery_c_margin_ratio <= 1.0):
            raise ValueError("Battery C margin ratio must be between 0.50 and 1.0.")
        if self.min_hover_twr <= 1.0:
            raise ValueError("Minimum hover TWR threshold must be > 1.0.")
        if self.recommended_agile_twr < self.min_hover_twr:
            raise ValueError("Recommended agile TWR must be >= min_hover_twr.")


@dataclass(frozen=True)
class PerformancePoint:
    """Single static thrust stand measurement or curve point for a motor-propeller pair."""

    throttle_pct: float  # [%] (0 to 100)
    voltage_v: float  # [V]
    current_a: float  # [A]
    thrust_gf: float  # [gf] (gram-force)
    power_w: float  # [W]
    rpm: float  # [rev/min]

    def __post_init__(self) -> None:
        if not (0.0 <= self.throttle_pct <= 100.0):
            raise ValueError(f"Throttle percentage ({self.throttle_pct}%) must be in [0, 100].")
        if self.voltage_v <= 0:
            raise ValueError("Measurement voltage must be strictly positive.")
        if self.current_a < 0:
            raise ValueError("Measurement current cannot be negative.")
        if self.thrust_gf < 0:
            raise ValueError("Measurement thrust cannot be negative.")
        if self.power_w < 0:
            raise ValueError("Measurement power cannot be negative.")
        if self.rpm < 0:
            raise ValueError("Measurement RPM cannot be negative.")

    @property
    def efficiency_gf_w(self) -> float:
        """Specific thrust (propulsive efficacy) in gram-force per Watt [gf/W]."""
        if self.power_w <= 1e-6:
            return 0.0
        return self.thrust_gf / self.power_w


@dataclass(frozen=True)
class PerformanceDataset:
    """Structured motor-propeller performance curve with full provenance metadata."""

    dataset_id: str
    motor_manufacturer: str
    motor_model: str
    motor_kv: float
    propeller_model: str
    propeller_diameter_in: float
    propeller_pitch_in: float
    test_voltage_v: float
    provenance: DataProvenance
    source_reference: str
    measurement_conditions: str
    points: List[PerformancePoint]
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.points or len(self.points) < 2:
            raise ValueError("PerformanceDataset requires at least 2 measurement points for interpolation.")
        # Ensure points are sorted by throttle_pct ascending
        sorted_pts = sorted(self.points, key=lambda p: p.throttle_pct)
        object.__setattr__(self, "points", sorted_pts)
        # Check for strictly increasing throttle values
        throttles = [p.throttle_pct for p in self.points]
        if len(set(throttles)) != len(throttles):
            raise ValueError("Duplicate throttle percentages are not permitted in PerformanceDataset.")

    @property
    def min_throttle_pct(self) -> float:
        return self.points[0].throttle_pct

    @property
    def max_throttle_pct(self) -> float:
        return self.points[-1].throttle_pct

    @property
    def min_thrust_gf(self) -> float:
        return min(p.thrust_gf for p in self.points)

    @property
    def max_thrust_gf(self) -> float:
        return max(p.thrust_gf for p in self.points)

    @property
    def display_label(self) -> str:
        return (
            f"{self.motor_manufacturer} {self.motor_model} KV{int(round(self.motor_kv))} | "
            f"{self.propeller_diameter_in:g}x{self.propeller_pitch_in:g}\" @ {self.test_voltage_v:g}V "
            f"[{self.provenance.value}]"
        )


@dataclass(frozen=True)
class PropulsionConfiguration:
    """Complete multirotor UAV propulsion configuration."""

    config_id: str
    name: str
    description: str
    motor: MotorSpec
    propeller: PropellerSpec
    esc: ESCSpec
    battery: BatterySpec
    airframe: AirframeSpec
    dataset_id: str
    margins: EngineeringMargins = field(default_factory=EngineeringMargins)
    created_at: Optional[str] = None
