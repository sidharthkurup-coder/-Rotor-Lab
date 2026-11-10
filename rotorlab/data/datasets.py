"""Structured propulsion datasets, default engineering presets, and CSV dataset parser.

CRITICAL DATA RELIABILITY POLICY:
- Manufacturer measurements are sourced from published T-Motor laboratory static test reports.
- Illustrative synthetic datasets are explicitly marked with `DataProvenance.ILLUSTRATIVE_SYNTHETIC`.
- User-imported CSV or manual tables are marked with `DataProvenance.USER_MEASURED`.
"""

from __future__ import annotations

import csv
import io
from typing import Dict, List

from rotorlab.models.domain import (
    AirframeSpec,
    BatterySpec,
    DataProvenance,
    EngineeringMargins,
    ESCSpec,
    MotorSpec,
    PerformanceDataset,
    PerformancePoint,
    PropellerSpec,
    PropulsionConfiguration,
)


def get_builtin_datasets() -> List[PerformanceDataset]:
    """Return built-in propulsion datasets with verified manufacturer tables and labeled illustrative curves."""
    return [
        # 1. T-Motor MN3508 KV380 | 14x4.8 CF @ 14.8V (4S) — Manufacturer Datasheet
        PerformanceDataset(
            dataset_id="tmotor_mn3508_kv380_14x48_14v8",
            motor_manufacturer="T-Motor",
            motor_model="MN3508",
            motor_kv=380.0,
            propeller_model="T-Motor 14x4.8 CF",
            propeller_diameter_in=14.0,
            propeller_pitch_in=4.8,
            test_voltage_v=14.8,
            provenance=DataProvenance.MANUFACTURER_DATASHEET,
            source_reference="T-Motor Navigator Series MN3508 KV380 Official Factory Static Test Table (14.8V, 14x4.8 CF)",
            measurement_conditions="Static bench test at sea-level standard atmosphere, regulated 14.8 V DC bus",
            points=[
                PerformancePoint(throttle_pct=50.0, voltage_v=14.8, current_a=1.3, thrust_gf=350.0, power_w=19.24, rpm=2700.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=14.8, current_a=2.9, thrust_gf=560.0, power_w=42.92, rpm=3500.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=14.8, current_a=4.0, thrust_gf=700.0, power_w=59.20, rpm=4000.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=14.8, current_a=5.2, thrust_gf=840.0, power_w=76.96, rpm=4500.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=14.8, current_a=6.3, thrust_gf=940.0, power_w=93.24, rpm=4700.0),
            ],
            notes="High-efficiency endurance multirotor motor-propeller combination.",
        ),
        # 2. T-Motor MN3110 KV470 | 13x4.4 CF @ 14.8V (4S) — Manufacturer Datasheet
        PerformanceDataset(
            dataset_id="tmotor_mn3110_kv470_13x44_14v8",
            motor_manufacturer="T-Motor",
            motor_model="MN3110",
            motor_kv=470.0,
            propeller_model="T-Motor 13x4.4 CF",
            propeller_diameter_in=13.0,
            propeller_pitch_in=4.4,
            test_voltage_v=14.8,
            provenance=DataProvenance.MANUFACTURER_DATASHEET,
            source_reference="T-Motor Navigator Series MN3110 KV470 Official Factory Static Test Table (14.8V, 13x4.4 CF)",
            measurement_conditions="Static bench test at sea-level standard atmosphere, regulated 14.8 V DC bus",
            points=[
                PerformancePoint(throttle_pct=50.0, voltage_v=14.8, current_a=1.5, thrust_gf=290.0, power_w=22.20, rpm=3300.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=14.8, current_a=2.6, thrust_gf=410.0, power_w=38.48, rpm=4000.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=14.8, current_a=3.5, thrust_gf=550.0, power_w=51.80, rpm=4600.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=14.8, current_a=4.9, thrust_gf=680.0, power_w=72.52, rpm=5200.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=14.8, current_a=5.8, thrust_gf=780.0, power_w=85.84, rpm=5500.0),
            ],
            notes="Lightweight reconnaissance quadcopter propulsion setup.",
        ),
        # 3. T-Motor U3 KV700 | 12x4 CF @ 14.8V (4S) — Manufacturer Datasheet
        PerformanceDataset(
            dataset_id="tmotor_u3_kv700_12x4_14v8",
            motor_manufacturer="T-Motor",
            motor_model="U3",
            motor_kv=700.0,
            propeller_model="T-Motor 12x4 CF",
            propeller_diameter_in=12.0,
            propeller_pitch_in=4.0,
            test_voltage_v=14.8,
            provenance=DataProvenance.MANUFACTURER_DATASHEET,
            source_reference="T-Motor U Power Series U3 KV700 Official Factory Static Test Table (14.8V, 12x4 CF)",
            measurement_conditions="Static bench test at sea-level standard atmosphere, regulated 14.8 V DC bus",
            points=[
                PerformancePoint(throttle_pct=50.0, voltage_v=14.8, current_a=3.8, thrust_gf=580.0, power_w=56.24, rpm=5000.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=14.8, current_a=7.4, thrust_gf=880.0, power_w=109.52, rpm=6300.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=14.8, current_a=10.3, thrust_gf=1100.0, power_w=152.44, rpm=7300.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=14.8, current_a=14.0, thrust_gf=1360.0, power_w=207.20, rpm=7700.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=14.8, current_a=16.8, thrust_gf=1600.0, power_w=248.64, rpm=8300.0),
            ],
            notes="Industrial medium-lift quad/hexacopter propulsion unit.",
        ),
        # 4. T-Motor Antigravity MN4004 KV300 | 13x4.4 CF @ 24.0V (6S) — Manufacturer Datasheet
        PerformanceDataset(
            dataset_id="tmotor_mn4004_kv300_13x44_24v",
            motor_manufacturer="T-Motor",
            motor_model="Antigravity MN4004",
            motor_kv=300.0,
            propeller_model="T-Motor 13x4.4 CF",
            propeller_diameter_in=13.0,
            propeller_pitch_in=4.4,
            test_voltage_v=24.0,
            provenance=DataProvenance.MANUFACTURER_DATASHEET,
            source_reference="T-Motor Antigravity MN4004 KV300 Official Factory Static Test Table (24.0V, 13x4.4 CF)",
            measurement_conditions="Static bench test at sea-level standard atmosphere, regulated 24.0 V DC (6S) bus",
            points=[
                PerformancePoint(throttle_pct=50.0, voltage_v=24.0, current_a=2.0, thrust_gf=544.0, power_w=48.00, rpm=3719.0),
                PerformancePoint(throttle_pct=55.0, voltage_v=24.0, current_a=2.5, thrust_gf=656.0, power_w=60.00, rpm=4528.0),
                PerformancePoint(throttle_pct=60.0, voltage_v=24.0, current_a=3.1, thrust_gf=753.0, power_w=74.40, rpm=4840.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=24.0, current_a=3.7, thrust_gf=853.0, power_w=88.80, rpm=5155.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=24.0, current_a=5.1, thrust_gf=1062.0, power_w=122.40, rpm=5451.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=24.0, current_a=6.8, thrust_gf=1286.0, power_w=163.20, rpm=6327.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=24.0, current_a=9.7, thrust_gf=1633.0, power_w=232.80, rpm=6515.0),
            ],
            notes="Ultralight 6S high-efficiency mapping/inspection propulsion unit.",
        ),
        # 5. T-Motor MN4014 KV400 | 15x5 CF @ 22.2V (6S) — Manufacturer Datasheet
        PerformanceDataset(
            dataset_id="tmotor_mn4014_kv400_15x5_22v2",
            motor_manufacturer="T-Motor",
            motor_model="MN4014",
            motor_kv=400.0,
            propeller_model="T-Motor 15x5 CF",
            propeller_diameter_in=15.0,
            propeller_pitch_in=5.0,
            test_voltage_v=22.2,
            provenance=DataProvenance.MANUFACTURER_DATASHEET,
            source_reference="T-Motor Navigator Series MN4014 KV400 Official Factory Static Test Table (22.2V, 15x5 CF)",
            measurement_conditions="Static bench test at sea-level standard atmosphere, regulated 22.2 V DC (6S) bus",
            points=[
                PerformancePoint(throttle_pct=50.0, voltage_v=22.2, current_a=5.7, thrust_gf=1250.0, power_w=126.54, rpm=4500.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=22.2, current_a=9.1, thrust_gf=1630.0, power_w=202.02, rpm=5200.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=22.2, current_a=12.0, thrust_gf=1950.0, power_w=266.40, rpm=5800.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=22.2, current_a=15.8, thrust_gf=2370.0, power_w=350.76, rpm=6400.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=22.2, current_a=18.7, thrust_gf=2620.0, power_w=415.14, rpm=6700.0),
            ],
            notes="Heavy-lift 6S hexacopter/octocopter propulsion with 15x5 carbon fiber propeller.",
        ),
        # 6. T-Motor MN4014 KV400 | 16x5.4 CF @ 22.2V (6S) — Manufacturer Datasheet
        PerformanceDataset(
            dataset_id="tmotor_mn4014_kv400_16x54_22v2",
            motor_manufacturer="T-Motor",
            motor_model="MN4014",
            motor_kv=400.0,
            propeller_model="T-Motor 16x5.4 CF",
            propeller_diameter_in=16.0,
            propeller_pitch_in=5.4,
            test_voltage_v=22.2,
            provenance=DataProvenance.MANUFACTURER_DATASHEET,
            source_reference="T-Motor Navigator Series MN4014 KV400 Official Factory Static Test Table (22.2V, 16x5.4 CF)",
            measurement_conditions="Static bench test at sea-level standard atmosphere, regulated 22.2 V DC (6S) bus",
            points=[
                PerformancePoint(throttle_pct=50.0, voltage_v=22.2, current_a=6.4, thrust_gf=1410.0, power_w=142.08, rpm=4200.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=22.2, current_a=11.0, thrust_gf=1920.0, power_w=244.20, rpm=5000.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=22.2, current_a=14.6, thrust_gf=2380.0, power_w=324.12, rpm=5500.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=22.2, current_a=19.1, thrust_gf=2790.0, power_w=424.02, rpm=6100.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=22.2, current_a=22.5, thrust_gf=3020.0, power_w=499.50, rpm=6300.0),
            ],
            notes="Heavy-lift 6S configuration with 16x5.4 CF propeller for higher static thrust.",
        ),
        # 7. T-Motor MN4014 KV400 | 17x5.8 CF @ 22.2V (6S) — Manufacturer Datasheet
        PerformanceDataset(
            dataset_id="tmotor_mn4014_kv400_17x58_22v2",
            motor_manufacturer="T-Motor",
            motor_model="MN4014",
            motor_kv=400.0,
            propeller_model="T-Motor 17x5.8 CF",
            propeller_diameter_in=17.0,
            propeller_pitch_in=5.8,
            test_voltage_v=22.2,
            provenance=DataProvenance.MANUFACTURER_DATASHEET,
            source_reference="T-Motor Navigator Series MN4014 KV400 Official Factory Static Test Table (22.2V, 17x5.8 CF)",
            measurement_conditions="Static bench test at sea-level standard atmosphere, regulated 22.2 V DC (6S) bus",
            points=[
                PerformancePoint(throttle_pct=50.0, voltage_v=22.2, current_a=7.6, thrust_gf=1530.0, power_w=168.72, rpm=4000.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=22.2, current_a=12.8, thrust_gf=2180.0, power_w=284.16, rpm=4800.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=22.2, current_a=16.7, thrust_gf=2550.0, power_w=370.74, rpm=5250.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=22.2, current_a=21.7, thrust_gf=3110.0, power_w=481.74, rpm=5700.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=22.2, current_a=25.7, thrust_gf=3360.0, power_w=570.54, rpm=6000.0),
            ],
            notes="Maximum-diameter 17-inch propeller load on MN4014 KV400; approaches 30A continuous motor ceiling.",
        ),
        # 8. Illustrative Synthetic Dataset — 5-inch High-KV FPV Quad (2207 KV1950 @ 22.2V)
        PerformanceDataset(
            dataset_id="synthetic_2207_kv1950_5x43_22v2",
            motor_manufacturer="Generic FPV (Illustrative)",
            motor_model="Pro-2207",
            motor_kv=1950.0,
            propeller_model="Tri-Blade 5.1x4.3 PC",
            propeller_diameter_in=5.1,
            propeller_pitch_in=4.3,
            test_voltage_v=22.2,
            provenance=DataProvenance.ILLUSTRATIVE_SYNTHETIC,
            source_reference="RotorLab Analytical Propeller Scaling Model (ILLUSTRATIVE SYNTHETIC DATA — NOT MANUFACTURER VERIFIED)",
            measurement_conditions="Synthetic full-range throttle curve (20%–100%) at 22.2 V (6S) for agile 5-inch quadcopter demonstration",
            points=[
                PerformancePoint(throttle_pct=20.0, voltage_v=22.2, current_a=1.6, thrust_gf=145.0, power_w=35.52, rpm=8200.0),
                PerformancePoint(throttle_pct=35.0, voltage_v=22.2, current_a=4.2, thrust_gf=330.0, power_w=93.24, rpm=12800.0),
                PerformancePoint(throttle_pct=50.0, voltage_v=22.2, current_a=8.5, thrust_gf=580.0, power_w=188.70, rpm=17200.0),
                PerformancePoint(throttle_pct=65.0, voltage_v=22.2, current_a=15.4, thrust_gf=890.0, power_w=341.88, rpm=21400.0),
                PerformancePoint(throttle_pct=75.0, voltage_v=22.2, current_a=21.8, thrust_gf=1120.0, power_w=483.96, rpm=24100.0),
                PerformancePoint(throttle_pct=85.0, voltage_v=22.2, current_a=29.5, thrust_gf=1340.0, power_w=654.90, rpm=26600.0),
                PerformancePoint(throttle_pct=100.0, voltage_v=22.2, current_a=39.2, thrust_gf=1580.0, power_w=870.24, rpm=29200.0),
            ],
            notes="Clearly labelled illustrative synthetic dataset demonstrating high disk loading and high C-rate FPV dynamics.",
        ),
    ]


def get_default_configurations() -> List[PropulsionConfiguration]:
    """Return pre-configured reference UAV architectures for immediate workstation exploration and comparison."""
    return [
        # Config 1: 4S Endurance Mapping Quadcopter (T-Motor MN3508 KV380 + 14x4.8 CF)
        PropulsionConfiguration(
            config_id="cfg_endurance_quad_4s",
            name="Surveyor-X4 Endurance Quad (4S 14in)",
            description="High-efficiency 4S survey quadcopter using T-Motor MN3508 KV380 motors and 14x4.8 CF propellers.",
            motor=MotorSpec(
                manufacturer="T-Motor",
                model="MN3508",
                kv_rating=380.0,
                max_continuous_current_a=14.0,
                max_continuous_power_w=310.0,
                internal_resistance_mohm=205.0,
                no_load_current_a=0.4,
                min_cells_s=3,
                max_cells_s=6,
                mass_g=103.0,
            ),
            propeller=PropellerSpec(
                manufacturer="T-Motor",
                model="T-Motor 14x4.8 CF",
                diameter_in=14.0,
                pitch_in=4.8,
                num_blades=2,
                material="Carbon Fiber (CF)",
                mass_g=17.0,
            ),
            esc=ESCSpec(
                name="T-Motor Flame 25A 4S-6S",
                continuous_current_a=25.0,
                peak_current_a=35.0,
                min_cells_s=3,
                max_cells_s=6,
                mass_g=26.0,
            ),
            battery=BatterySpec(
                name="4S 6000mAh 25C LiPo Pack",
                cell_count_s=4,
                nominal_voltage_v=14.8,
                operating_voltage_v=14.8,
                capacity_mah=6000.0,
                continuous_c_rating=25.0,
                burst_c_rating=50.0,
                usable_capacity_fraction=0.80,
                internal_resistance_per_cell_mohm=3.5,
                mass_g=580.0,
            ),
            airframe=AirframeSpec(
                frame_type="Quadcopter (X4)",
                num_motors=4,
                aircraft_dry_mass_kg=1.35,
                payload_mass_kg=0.35,
                avionics_power_w=8.0,
                operating_throttle_pct=65.0,
                altitude_m=0.0,
                temp_offset_c=0.0,
            ),
            dataset_id="tmotor_mn3508_kv380_14x48_14v8",
        ),
        # Config 2: 4S Industrial Tactical Quadcopter (T-Motor U3 KV700 + 12x4 CF)
        PropulsionConfiguration(
            config_id="cfg_industrial_u3_quad_4s",
            name="Tactical-U3 Inspection Quad (4S 12in)",
            description="Higher thrust-density 4S quadcopter using T-Motor U3 KV700 motors and 12x4 CF propellers.",
            motor=MotorSpec(
                manufacturer="T-Motor",
                model="U3",
                kv_rating=700.0,
                max_continuous_current_a=25.0,
                max_continuous_power_w=500.0,
                internal_resistance_mohm=50.0,
                no_load_current_a=0.7,
                min_cells_s=3,
                max_cells_s=4,
                mass_g=128.0,
            ),
            propeller=PropellerSpec(
                manufacturer="T-Motor",
                model="T-Motor 12x4 CF",
                diameter_in=12.0,
                pitch_in=4.0,
                num_blades=2,
                material="Carbon Fiber (CF)",
                mass_g=14.5,
            ),
            esc=ESCSpec(
                name="T-Motor Air 40A 3S-6S",
                continuous_current_a=40.0,
                peak_current_a=60.0,
                min_cells_s=3,
                max_cells_s=6,
                mass_g=32.0,
            ),
            battery=BatterySpec(
                name="4S 8000mAh 30C LiPo Pack",
                cell_count_s=4,
                nominal_voltage_v=14.8,
                operating_voltage_v=14.8,
                capacity_mah=8000.0,
                continuous_c_rating=30.0,
                burst_c_rating=60.0,
                usable_capacity_fraction=0.80,
                internal_resistance_per_cell_mohm=3.0,
                mass_g=760.0,
            ),
            airframe=AirframeSpec(
                frame_type="Quadcopter (X4)",
                num_motors=4,
                aircraft_dry_mass_kg=1.85,
                payload_mass_kg=0.75,
                avionics_power_w=12.0,
                operating_throttle_pct=65.0,
                altitude_m=0.0,
                temp_offset_c=0.0,
            ),
            dataset_id="tmotor_u3_kv700_12x4_14v8",
        ),
        # Config 3: 6S Heavy-Lift Hexacopter (T-Motor MN4014 KV400 + 16x5.4 CF)
        PropulsionConfiguration(
            config_id="cfg_heavylift_hexa_6s",
            name="Atlas-X6 Heavy-Lift Hexa (6S 16in)",
            description="6-rotor heavy-lift LiDAR/cinema hexacopter powered by T-Motor MN4014 KV400 on 6S with 16x5.4 CF props.",
            motor=MotorSpec(
                manufacturer="T-Motor",
                model="MN4014",
                kv_rating=400.0,
                max_continuous_current_a=30.0,
                max_continuous_power_w=900.0,
                internal_resistance_mohm=67.0,
                no_load_current_a=0.9,
                min_cells_s=4,
                max_cells_s=8,
                mass_g=171.0,
            ),
            propeller=PropellerSpec(
                manufacturer="T-Motor",
                model="T-Motor 16x5.4 CF",
                diameter_in=16.0,
                pitch_in=5.4,
                num_blades=2,
                material="Carbon Fiber (CF)",
                mass_g=28.0,
            ),
            esc=ESCSpec(
                name="T-Motor Flame 60A HV 6S-12S",
                continuous_current_a=60.0,
                peak_current_a=80.0,
                min_cells_s=6,
                max_cells_s=12,
                mass_g=54.0,
            ),
            battery=BatterySpec(
                name="6S 16000mAh 25C Heavy-Lift LiPo",
                cell_count_s=6,
                nominal_voltage_v=22.2,
                operating_voltage_v=22.2,
                capacity_mah=16000.0,
                continuous_c_rating=25.0,
                burst_c_rating=50.0,
                usable_capacity_fraction=0.80,
                internal_resistance_per_cell_mohm=2.2,
                mass_g=1950.0,
            ),
            airframe=AirframeSpec(
                frame_type="Hexacopter (X6)",
                num_motors=6,
                aircraft_dry_mass_kg=4.80,
                payload_mass_kg=2.70,
                avionics_power_w=18.0,
                operating_throttle_pct=65.0,
                altitude_m=0.0,
                temp_offset_c=0.0,
            ),
            dataset_id="tmotor_mn4014_kv400_16x54_22v2",
        ),
        # Config 4: 6S Ultralight Long-Endurance Quad (T-Motor Antigravity MN4004 KV300 + 13x4.4 CF)
        PropulsionConfiguration(
            config_id="cfg_antigravity_quad_6s",
            name="Valkyrie-4004 Long-Range Quad (6S 13in)",
            description="Ultralight 6S quadcopter using T-Motor Antigravity MN4004 KV300 motors and 13x4.4 CF propellers.",
            motor=MotorSpec(
                manufacturer="T-Motor",
                model="Antigravity MN4004",
                kv_rating=300.0,
                max_continuous_current_a=12.0,
                max_continuous_power_w=260.0,
                internal_resistance_mohm=452.0,
                no_load_current_a=0.2,
                min_cells_s=4,
                max_cells_s=6,
                mass_g=53.0,
            ),
            propeller=PropellerSpec(
                manufacturer="T-Motor",
                model="T-Motor 13x4.4 CF",
                diameter_in=13.0,
                pitch_in=4.4,
                num_blades=2,
                material="Carbon Fiber (CF)",
                mass_g=15.0,
            ),
            esc=ESCSpec(
                name="T-Motor F35A 6S ESC",
                continuous_current_a=35.0,
                peak_current_a=45.0,
                min_cells_s=3,
                max_cells_s=6,
                mass_g=12.0,
            ),
            battery=BatterySpec(
                name="6S 7000mAh Li-Ion/LiPo Hybrid Pack",
                cell_count_s=6,
                nominal_voltage_v=22.2,
                operating_voltage_v=24.0,
                capacity_mah=7000.0,
                continuous_c_rating=15.0,
                burst_c_rating=30.0,
                usable_capacity_fraction=0.80,
                internal_resistance_per_cell_mohm=4.5,
                mass_g=820.0,
            ),
            airframe=AirframeSpec(
                frame_type="Quadcopter (X4)",
                num_motors=4,
                aircraft_dry_mass_kg=1.60,
                payload_mass_kg=0.60,
                avionics_power_w=10.0,
                operating_throttle_pct=65.0,
                altitude_m=0.0,
                temp_offset_c=0.0,
            ),
            dataset_id="tmotor_mn4004_kv300_13x44_24v",
        ),
    ]


def parse_csv_performance_dataset(
    csv_content: str,
    dataset_id: str,
    motor_manufacturer: str,
    motor_model: str,
    motor_kv: float,
    propeller_model: str,
    propeller_diameter_in: float,
    propeller_pitch_in: float,
    test_voltage_v: float,
    provenance: DataProvenance = DataProvenance.USER_MEASURED,
    source_reference: str = "User CSV Import",
    measurement_conditions: str = "User-specified test bench conditions",
) -> PerformanceDataset:
    """Parse and validate a CSV string into a structured `PerformanceDataset`.

    Required CSV columns (case-insensitive, flexible aliases):
    - throttle_pct (or throttle, throttle_%)
    - thrust_gf (or thrust, thrust_g)
    - current_a (or current, amps)
    - rpm (or speed_rpm)
    Optional CSV columns:
    - voltage_v (or voltage) -> defaults to `test_voltage_v`
    - power_w (or power, watts) -> defaults to `voltage_v * current_a`
    """
    if not csv_content or not csv_content.strip():
        raise ValueError("CSV content cannot be empty.")

    non_comment_lines = [
        line for line in csv_content.splitlines() if line.strip() and not line.strip().startswith("#")
    ]
    if not non_comment_lines:
        raise ValueError("CSV content contains no valid header or data rows.")

    reader = csv.DictReader(io.StringIO("\n".join(non_comment_lines)))
    if not reader.fieldnames:
        raise ValueError("CSV header row is missing.")

    # Map normalized header names
    header_map: Dict[str, str] = {h.strip().lower(): h for h in reader.fieldnames if h}

    def _find_col(aliases: List[str]) -> str | None:
        for alias in aliases:
            if alias in header_map:
                return header_map[alias]
        return None

    col_th = _find_col(["throttle_pct", "throttle", "throttle_%", "throttle_percent"])
    col_tr = _find_col(["thrust_gf", "thrust_g", "thrust", "thrust_grams"])
    col_cur = _find_col(["current_a", "current", "amps", "amperes"])
    col_rpm = _find_col(["rpm", "speed_rpm", "motor_rpm"])
    col_v = _find_col(["voltage_v", "voltage", "volts"])
    col_p = _find_col(["power_w", "power", "watts"])

    missing = []
    if not col_th:
        missing.append("throttle_pct")
    if not col_tr:
        missing.append("thrust_gf")
    if not col_cur:
        missing.append("current_a")
    if not col_rpm:
        missing.append("rpm")
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}.")

    points: List[PerformancePoint] = []
    for row_idx, row in enumerate(reader, start=2):
        try:
            th_val = float(row[col_th])  # type: ignore[index]
            tr_val = float(row[col_tr])  # type: ignore[index]
            cur_val = float(row[col_cur])  # type: ignore[index]
            rpm_val = float(row[col_rpm])  # type: ignore[index]
            v_val = float(row[col_v]) if col_v and row.get(col_v) else test_voltage_v
            p_val = float(row[col_p]) if col_p and row.get(col_p) else (v_val * cur_val)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid numeric value on CSV row {row_idx}: {exc}") from exc

        points.append(
            PerformancePoint(
                throttle_pct=th_val,
                voltage_v=v_val,
                current_a=cur_val,
                thrust_gf=tr_val,
                power_w=p_val,
                rpm=rpm_val,
            )
        )

    return PerformanceDataset(
        dataset_id=dataset_id,
        motor_manufacturer=motor_manufacturer,
        motor_model=motor_model,
        motor_kv=motor_kv,
        propeller_model=propeller_model,
        propeller_diameter_in=propeller_diameter_in,
        propeller_pitch_in=propeller_pitch_in,
        test_voltage_v=test_voltage_v,
        provenance=provenance,
        source_reference=source_reference,
        measurement_conditions=measurement_conditions,
        points=points,
    )
