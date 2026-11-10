"""Dimensionally consistent SI unit conversions and atmospheric physics utilities.

All internal RotorLab engineering calculations operate in strict SI units
(Newtons, kilograms, meters, seconds, Volts, Amperes, Watts, Joules) or
explicitly documented aerospace engineering units (Watt-hours, Ampere-hours).
"""

from __future__ import annotations

import math

# Standard gravitational acceleration (CODATA / ISO 80000-3) [m/s^2]
STANDARD_GRAVITY_M_S2: float = 9.80665

# Standard sea-level ISA parameters
ISA_SEA_LEVEL_PRESSURE_PA: float = 101325.0
ISA_SEA_LEVEL_TEMP_K: float = 288.15
ISA_TEMP_LAPSE_RATE_K_M: float = 0.0065
SPECIFIC_GAS_CONSTANT_DRY_AIR: float = 287.05287

# Conversion factors
GRAMS_PER_KG: float = 1000.0
METERS_PER_INCH: float = 0.0254
LBS_TO_KG: float = 0.45359237
OZ_TO_KG: float = 0.028349523125
MAH_PER_AH: float = 1000.0
SECONDS_PER_MINUTE: float = 60.0
SECONDS_PER_HOUR: float = 3600.0


def gf_to_newtons(thrust_gf: float, g: float = STANDARD_GRAVITY_M_S2) -> float:
    """Convert gram-force (gf) to Newtons (N).

    Formula: F [N] = (m [g] / 1000) * g [m/s^2]
    """
    if g <= 0:
        raise ValueError("Gravitational acceleration g must be strictly positive.")
    return (thrust_gf / GRAMS_PER_KG) * g


def newtons_to_gf(force_n: float, g: float = STANDARD_GRAVITY_M_S2) -> float:
    """Convert Newtons (N) to gram-force (gf).

    Formula: m [gf] = (F [N] / g [m/s^2]) * 1000
    """
    if g <= 0:
        raise ValueError("Gravitational acceleration g must be strictly positive.")
    return (force_n / g) * GRAMS_PER_KG


def kgf_to_newtons(thrust_kgf: float, g: float = STANDARD_GRAVITY_M_S2) -> float:
    """Convert kilogram-force (kgf) to Newtons (N)."""
    if g <= 0:
        raise ValueError("Gravitational acceleration g must be strictly positive.")
    return thrust_kgf * g


def newtons_to_kgf(force_n: float, g: float = STANDARD_GRAVITY_M_S2) -> float:
    """Convert Newtons (N) to kilogram-force (kgf)."""
    if g <= 0:
        raise ValueError("Gravitational acceleration g must be strictly positive.")
    return force_n / g


def lbf_to_newtons(force_lbf: float, g: float = STANDARD_GRAVITY_M_S2) -> float:
    """Convert pound-force (lbf) to Newtons (N)."""
    if g <= 0:
        raise ValueError("Gravitational acceleration g must be strictly positive.")
    return force_lbf * LBS_TO_KG * g


def newtons_to_lbf(force_n: float, g: float = STANDARD_GRAVITY_M_S2) -> float:
    """Convert Newtons (N) to pound-force (lbf)."""
    if g <= 0:
        raise ValueError("Gravitational acceleration g must be strictly positive.")
    return force_n / (LBS_TO_KG * g)


def mass_kg_to_weight_n(mass_kg: float, g: float = STANDARD_GRAVITY_M_S2) -> float:
    """Calculate gravitational weight force in Newtons from mass in kilograms.

    Formula: W [N] = m [kg] * g [m/s^2]
    """
    if mass_kg < 0:
        raise ValueError("Mass cannot be negative.")
    if g <= 0:
        raise ValueError("Gravitational acceleration g must be strictly positive.")
    return mass_kg * g


def grams_to_kg(mass_g: float) -> float:
    """Convert mass in grams (g) to kilograms (kg)."""
    return mass_g / GRAMS_PER_KG


def kg_to_grams(mass_kg: float) -> float:
    """Convert mass in kilograms (kg) to grams (g)."""
    return mass_kg * GRAMS_PER_KG


def lbs_to_kg(mass_lbs: float) -> float:
    """Convert mass in avoirdupois pounds (lb) to kilograms (kg)."""
    return mass_lbs * LBS_TO_KG


def kg_to_lbs(mass_kg: float) -> float:
    """Convert mass in kilograms (kg) to avoirdupois pounds (lb)."""
    return mass_kg / LBS_TO_KG


def inches_to_meters(length_in: float) -> float:
    """Convert length in inches (in) to meters (m)."""
    return length_in * METERS_PER_INCH


def meters_to_inches(length_m: float) -> float:
    """Convert length in meters (m) to inches (in)."""
    return length_m / METERS_PER_INCH


def mm_to_inches(length_mm: float) -> float:
    """Convert length in millimeters (mm) to inches (in)."""
    return length_mm / 25.4


def inches_to_mm(length_in: float) -> float:
    """Convert length in inches (in) to millimeters (mm)."""
    return length_in * 25.4


def mah_to_ah(capacity_mah: float) -> float:
    """Convert electrical charge capacity from milliampere-hours (mAh) to Ampere-hours (Ah)."""
    return capacity_mah / MAH_PER_AH


def ah_to_mah(capacity_ah: float) -> float:
    """Convert electrical charge capacity from Ampere-hours (Ah) to milliampere-hours (mAh)."""
    return capacity_ah * MAH_PER_AH


def rpm_to_rad_s(rpm: float) -> float:
    """Convert rotational speed from revolutions per minute (RPM) to radians per second (rad/s).

    Formula: omega [rad/s] = RPM * (2 * pi / 60)
    """
    return rpm * (2.0 * math.pi / SECONDS_PER_MINUTE)


def rad_s_to_rpm(omega_rad_s: float) -> float:
    """Convert rotational speed from radians per second (rad/s) to revolutions per minute (RPM)."""
    return omega_rad_s * (SECONDS_PER_MINUTE / (2.0 * math.pi))


def calculate_rotor_disk_area_m2(diameter_in: float) -> float:
    """Calculate single rotor swept disk area in square meters (m^2) from diameter in inches.

    Formula: A [m^2] = pi * (D [m] / 2)^2
    """
    if diameter_in <= 0:
        raise ValueError("Propeller diameter must be strictly positive.")
    diameter_m = inches_to_meters(diameter_in)
    return math.pi * (diameter_m / 2.0) ** 2


def calculate_tip_speed_m_s(diameter_in: float, rpm: float) -> float:
    """Calculate propeller blade tip speed in meters per second (m/s).

    Formula: V_tip [m/s] = omega [rad/s] * R [m] = (RPM * 2 * pi / 60) * (D [m] / 2)
    """
    if diameter_in <= 0:
        raise ValueError("Propeller diameter must be strictly positive.")
    if rpm < 0:
        raise ValueError("RPM cannot be negative.")
    radius_m = inches_to_meters(diameter_in) / 2.0
    return rpm_to_rad_s(rpm) * radius_m


def calculate_isa_air_density(altitude_m: float = 0.0, temp_offset_c: float = 0.0) -> float:
    """Calculate dry air density rho [kg/m^3] in the troposphere using the International Standard Atmosphere (ISA).

    Valid for geopotential altitudes up to 11,000 m.
    Formula:
        T_std(h) = T_0 - L * h
        p(h) = p_0 * (1 - L * h / T_0)^(g_0 / (R * L))
        T_actual = T_std(h) + delta_T
        rho = p(h) / (R * T_actual)
    """
    if altitude_m < -500.0 or altitude_m > 11000.0:
        raise ValueError("Altitude must be within tropospheric bounds (-500 m to 11,000 m).")

    t_std_k = ISA_SEA_LEVEL_TEMP_K - ISA_TEMP_LAPSE_RATE_K_M * altitude_m
    exponent = STANDARD_GRAVITY_M_S2 / (SPECIFIC_GAS_CONSTANT_DRY_AIR * ISA_TEMP_LAPSE_RATE_K_M)
    pressure_pa = ISA_SEA_LEVEL_PRESSURE_PA * ((t_std_k / ISA_SEA_LEVEL_TEMP_K) ** exponent)
    t_actual_k = t_std_k + temp_offset_c
    if t_actual_k <= 0:
        raise ValueError("Absolute air temperature must be strictly positive.")
    return pressure_pa / (SPECIFIC_GAS_CONSTANT_DRY_AIR * t_actual_k)
