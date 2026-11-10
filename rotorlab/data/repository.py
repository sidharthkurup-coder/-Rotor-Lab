"""SQLite persistence repository for RotorLab configurations and custom performance datasets."""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from rotorlab.data.datasets import get_builtin_datasets, get_default_configurations
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


class RotorLabRepository:
    """Persistent SQLite storage for propulsion configurations and user performance datasets."""

    def __init__(self, db_path: str | Path = "rotorlab_workspace.db") -> None:
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._persistent_conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._persistent_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._init_schema()
        self.ensure_builtin_presets()
        self.ensure_default_components()

    def _get_conn(self) -> sqlite3.Connection:
        if self._is_memory and self._persistent_conn is not None:
            return self._persistent_conn
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        if not self._is_memory:
            conn.close()

    def _init_schema(self) -> None:
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS configurations (
                        config_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS custom_datasets (
                        dataset_id TEXT PRIMARY KEY,
                        motor_manufacturer TEXT NOT NULL,
                        motor_model TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS components (
                        component_id TEXT PRIMARY KEY,
                        component_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        manufacturer TEXT NOT NULL,
                        provenance TEXT NOT NULL,
                        source_reference TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
        finally:
            self._close_conn(conn)

    @staticmethod
    def builtin_preset_ids() -> set[str]:
        """Return the set of protected built-in reference configuration IDs."""
        return {cfg.config_id for cfg in get_default_configurations()}

    def ensure_builtin_presets(self) -> None:
        """Ensure all 4 built-in reference configurations exist in the database."""
        existing_ids: set[str] = set()
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT config_id FROM configurations")
            existing_ids = {row[0] for row in cursor.fetchall()}
        finally:
            self._close_conn(conn)

        for cfg in get_default_configurations():
            if cfg.config_id not in existing_ids:
                self.save_configuration(cfg)

    def reset_builtin_presets(self) -> None:
        """Restore all 4 built-in reference configurations to their factory specifications."""
        for cfg in get_default_configurations():
            self.save_configuration(cfg)

    def seed_defaults_if_empty(self) -> None:
        """Ensure built-in default engineering configurations are seeded."""
        self.ensure_builtin_presets()

    @staticmethod
    def _serialize_config(cfg: PropulsionConfiguration) -> str:
        data = dataclasses.asdict(cfg)
        return json.dumps(data)

    @staticmethod
    def _deserialize_config(payload_json: str, created_at: str) -> PropulsionConfiguration:
        d = json.loads(payload_json)
        return PropulsionConfiguration(
            config_id=d["config_id"],
            name=d["name"],
            description=d["description"],
            motor=MotorSpec(**d["motor"]),
            propeller=PropellerSpec(**d["propeller"]),
            esc=ESCSpec(**d["esc"]),
            battery=BatterySpec(**d["battery"]),
            airframe=AirframeSpec(**d["airframe"]),
            dataset_id=d["dataset_id"],
            margins=EngineeringMargins(**d.get("margins", {})),
            created_at=d.get("created_at") or created_at,
        )

    def save_configuration(self, config: PropulsionConfiguration) -> PropulsionConfiguration:
        """Insert or update a propulsion configuration in SQLite."""
        now_iso = config.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        cfg_with_ts = dataclasses.replace(config, created_at=now_iso)
        payload = self._serialize_config(cfg_with_ts)

        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO configurations (config_id, name, description, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(config_id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        payload_json = excluded.payload_json,
                        created_at = excluded.created_at
                    """,
                    (cfg_with_ts.config_id, cfg_with_ts.name, cfg_with_ts.description, payload, now_iso),
                )
        finally:
            self._close_conn(conn)
        return cfg_with_ts

    def list_configurations(self) -> List[PropulsionConfiguration]:
        """Return all stored propulsion configurations ordered by creation/update time."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT payload_json, created_at FROM configurations ORDER BY rowid ASC"
            )
            rows = cursor.fetchall()
        finally:
            self._close_conn(conn)
        return [self._deserialize_config(row[0], row[1]) for row in rows]

    def get_configuration(self, config_id: str) -> Optional[PropulsionConfiguration]:
        """Retrieve a specific configuration by its ID."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT payload_json, created_at FROM configurations WHERE config_id = ?",
                (config_id,),
            )
            row = cursor.fetchone()
        finally:
            self._close_conn(conn)
        if not row:
            return None
        return self._deserialize_config(row[0], row[1])

    def duplicate_configuration(
        self, source_config_id: str, new_name: Optional[str] = None
    ) -> PropulsionConfiguration:
        """Duplicate an existing configuration under a new unique ID."""
        src = self.get_configuration(source_config_id)
        if src is None:
            raise KeyError(f"Configuration '{source_config_id}' not found.")
        new_id = f"cfg_{uuid.uuid4().hex[:8]}"
        dup_name = new_name.strip() if new_name and new_name.strip() else f"{src.name} (Copy)"
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        dup_cfg = dataclasses.replace(
            src,
            config_id=new_id,
            name=dup_name,
            created_at=now_iso,
        )
        return self.save_configuration(dup_cfg)

    def delete_configuration(self, config_id: str) -> bool:
        """Delete a custom configuration by ID. Built-in reference presets are protected and cannot be deleted."""
        if config_id in self.builtin_preset_ids():
            return False
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM configurations WHERE config_id = ?",
                    (config_id,),
                )
                deleted = cursor.rowcount > 0
        finally:
            self._close_conn(conn)
        return deleted

    def save_custom_dataset(self, dataset: PerformanceDataset) -> PerformanceDataset:
        """Persist a user-entered or CSV-imported `PerformanceDataset` in SQLite."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        data = dataclasses.asdict(dataset)
        data["provenance"] = dataset.provenance.value
        payload = json.dumps(data)

        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO custom_datasets (dataset_id, motor_manufacturer, motor_model, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(dataset_id) DO UPDATE SET
                        motor_manufacturer = excluded.motor_manufacturer,
                        motor_model = excluded.motor_model,
                        payload_json = excluded.payload_json,
                        created_at = excluded.created_at
                    """,
                    (
                        dataset.dataset_id,
                        dataset.motor_manufacturer,
                        dataset.motor_model,
                        payload,
                        now_iso,
                    ),
                )
        finally:
            self._close_conn(conn)
        return dataset

    def list_all_datasets(self) -> List[PerformanceDataset]:
        """Return all built-in datasets plus all user-saved custom datasets."""
        builtin = get_builtin_datasets()
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT payload_json FROM custom_datasets ORDER BY rowid ASC"
            )
            rows = cursor.fetchall()
        finally:
            self._close_conn(conn)

        custom_list: List[PerformanceDataset] = []
        for (payload_json,) in rows:
            d = json.loads(payload_json)
            pts = [PerformancePoint(**pt) for pt in d["points"]]
            custom_list.append(
                PerformanceDataset(
                    dataset_id=d["dataset_id"],
                    motor_manufacturer=d["motor_manufacturer"],
                    motor_model=d["motor_model"],
                    motor_kv=float(d["motor_kv"]),
                    propeller_model=d["propeller_model"],
                    propeller_diameter_in=float(d["propeller_diameter_in"]),
                    propeller_pitch_in=float(d["propeller_pitch_in"]),
                    test_voltage_v=float(d["test_voltage_v"]),
                    provenance=DataProvenance(d["provenance"]),
                    source_reference=d["source_reference"],
                    measurement_conditions=d["measurement_conditions"],
                    points=pts,
                    notes=d.get("notes", ""),
                )
            )

        # Deduplicate by dataset_id (custom overrides builtin if same ID)
        by_id = {ds.dataset_id: ds for ds in builtin}
        for ds in custom_list:
            by_id[ds.dataset_id] = ds
        return list(by_id.values())

    def get_dataset(self, dataset_id: str) -> Optional[PerformanceDataset]:
        """Find a dataset by ID across built-in and custom datasets."""
        for ds in self.list_all_datasets():
            if ds.dataset_id == dataset_id:
                return ds
        return None

    def ensure_default_components(self) -> None:
        """Seed default components from factory reference configurations if catalog is empty."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT count(*) FROM components")
            count = cursor.fetchone()[0]
        finally:
            self._close_conn(conn)

        if count > 0:
            return

        for cfg in get_default_configurations():
            # Seed motor
            motor_id = f"cmp_motor_{re.sub(r'[^a-zA-Z0-9_]', '_', cfg.motor.model.lower())}"
            self.save_component(
                component_type="motor",
                spec=cfg.motor,
                provenance=DataProvenance.MANUFACTURER_DATASHEET,
                source_reference=f"Reference Preset: {cfg.name}",
                component_id=motor_id,
            )
            # Seed propeller
            prop_id = f"cmp_prop_{re.sub(r'[^a-zA-Z0-9_]', '_', cfg.propeller.model.lower())}_{cfg.propeller.code.replace('x', '_')}"
            self.save_component(
                component_type="propeller",
                spec=cfg.propeller,
                provenance=DataProvenance.MANUFACTURER_DATASHEET,
                source_reference=f"Reference Preset: {cfg.name}",
                component_id=prop_id,
            )
            # Seed ESC
            esc_id = f"cmp_esc_{re.sub(r'[^a-zA-Z0-9_]', '_', cfg.esc.name.lower())}"
            self.save_component(
                component_type="esc",
                spec=cfg.esc,
                provenance=DataProvenance.MANUFACTURER_DATASHEET,
                source_reference=f"Reference Preset: {cfg.name}",
                component_id=esc_id,
            )
            # Seed Battery
            bat_id = f"cmp_bat_{re.sub(r'[^a-zA-Z0-9_]', '_', cfg.battery.name.lower())}"
            self.save_component(
                component_type="battery",
                spec=cfg.battery,
                provenance=DataProvenance.MANUFACTURER_DATASHEET,
                source_reference=f"Reference Preset: {cfg.name}",
                component_id=bat_id,
            )

    def save_component(
        self,
        component_type: str,
        spec: Any,
        provenance: DataProvenance | str = DataProvenance.USER_MEASURED,
        source_reference: str = "",
        component_id: Optional[str] = None,
    ) -> str:
        """Persist a component in SQLite with full provenance tracking."""
        prov_val = provenance.value if isinstance(provenance, DataProvenance) else str(provenance)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if dataclasses.is_dataclass(spec):
            spec_dict = dataclasses.asdict(spec)
        elif isinstance(spec, dict):
            spec_dict = dict(spec)
        else:
            raise ValueError(f"Unsupported component spec type: {type(spec)}")

        ctype = component_type.lower().strip()
        if ctype == "motor":
            mfg = spec_dict.get("manufacturer", "Generic")
            mdl = spec_dict.get("model", "Motor")
            name = f"{mfg} {mdl} (KV{int(round(float(spec_dict.get('kv_rating', 0))))})"
        elif ctype == "propeller":
            mfg = spec_dict.get("manufacturer", "Generic")
            mdl = spec_dict.get("model", "Propeller")
            dia = spec_dict.get("diameter_in", 0)
            pit = spec_dict.get("pitch_in", 0)
            name = f"{mfg} {mdl} ({dia}x{pit}\")"
        elif ctype == "esc":
            name = spec_dict.get("name", "Electronic Speed Controller")
            mfg = name.split()[0] if name else "Generic"
        elif ctype == "battery":
            name = spec_dict.get("name", "LiPo Battery")
            mfg = name.split()[0] if name else "Generic"
        else:
            name = spec_dict.get("name", f"Component {ctype}")
            mfg = spec_dict.get("manufacturer", "Generic")

        cid = component_id or f"cmp_{ctype}_{uuid.uuid4().hex[:8]}"
        payload = json.dumps(spec_dict)

        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO components (component_id, component_type, name, manufacturer, provenance, source_reference, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(component_id) DO UPDATE SET
                        component_type = excluded.component_type,
                        name = excluded.name,
                        manufacturer = excluded.manufacturer,
                        provenance = excluded.provenance,
                        source_reference = excluded.source_reference,
                        payload_json = excluded.payload_json,
                        created_at = excluded.created_at
                    """,
                    (cid, ctype, name, mfg, prov_val, source_reference, payload, now_iso),
                )
        finally:
            self._close_conn(conn)
        return cid

    def list_components(self, component_type: Optional[str] = None) -> List[dict]:
        """List stored components, optionally filtered by type ('motor', 'propeller', 'esc', 'battery')."""
        conn = self._get_conn()
        try:
            if component_type:
                cursor = conn.execute(
                    "SELECT component_id, component_type, name, manufacturer, provenance, source_reference, payload_json, created_at FROM components WHERE component_type = ? ORDER BY rowid ASC",
                    (component_type.lower().strip(),),
                )
            else:
                cursor = conn.execute(
                    "SELECT component_id, component_type, name, manufacturer, provenance, source_reference, payload_json, created_at FROM components ORDER BY rowid ASC"
                )
            rows = cursor.fetchall()
        finally:
            self._close_conn(conn)

        results = []
        for r in rows:
            results.append(
                {
                    "component_id": r[0],
                    "component_type": r[1],
                    "name": r[2],
                    "manufacturer": r[3],
                    "provenance": r[4],
                    "source_reference": r[5],
                    "spec": json.loads(r[6]),
                    "created_at": r[7],
                }
            )
        return results

    def get_component(self, component_id: str) -> Optional[dict]:
        """Retrieve a single component record by ID."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT component_id, component_type, name, manufacturer, provenance, source_reference, payload_json, created_at FROM components WHERE component_id = ?",
                (component_id,),
            )
            r = cursor.fetchone()
        finally:
            self._close_conn(conn)
        if not r:
            return None
        return {
            "component_id": r[0],
            "component_type": r[1],
            "name": r[2],
            "manufacturer": r[3],
            "provenance": r[4],
            "source_reference": r[5],
            "spec": json.loads(r[6]),
            "created_at": r[7],
        }

    def delete_component(self, component_id: str) -> bool:
        """Delete a component by ID from the catalog."""
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM components WHERE component_id = ?",
                    (component_id,),
                )
                deleted = cursor.rowcount > 0
        finally:
            self._close_conn(conn)
        return deleted

    def import_components_csv(
        self,
        csv_text: str,
        component_type: str,
        provenance: DataProvenance | str = DataProvenance.USER_MEASURED,
        source_reference: str = "CSV Import",
    ) -> int:
        """Parse CSV content and import components of the specified type."""
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        imported = 0
        ctype = component_type.lower().strip()

        for row in reader:
            clean_row = {k.strip(): v.strip() for k, v in row.items() if k and v}
            if not clean_row:
                continue

            if ctype == "motor":
                spec = MotorSpec(
                    manufacturer=clean_row["manufacturer"],
                    model=clean_row["model"],
                    kv_rating=float(clean_row["kv_rating"]),
                    max_continuous_current_a=float(clean_row["max_continuous_current_a"]),
                    max_continuous_power_w=float(clean_row["max_continuous_power_w"]),
                    internal_resistance_mohm=float(clean_row.get("internal_resistance_mohm", 100.0)),
                    no_load_current_a=float(clean_row.get("no_load_current_a", 0.5)),
                    min_cells_s=int(clean_row.get("min_cells_s", 3)),
                    max_cells_s=int(clean_row.get("max_cells_s", 6)),
                    mass_g=float(clean_row.get("mass_g", 100.0)),
                )
            elif ctype == "propeller":
                spec = PropellerSpec(
                    manufacturer=clean_row.get("manufacturer", "Generic"),
                    model=clean_row["model"],
                    diameter_in=float(clean_row["diameter_in"]),
                    pitch_in=float(clean_row["pitch_in"]),
                    num_blades=int(clean_row.get("num_blades", 2)),
                    material=clean_row.get("material", "Carbon Fiber (CF)"),
                    mass_g=float(clean_row.get("mass_g", 18.0)),
                )
            elif ctype == "esc":
                spec = ESCSpec(
                    name=clean_row["name"],
                    continuous_current_a=float(clean_row["continuous_current_a"]),
                    peak_current_a=float(clean_row["peak_current_a"]),
                    min_cells_s=int(clean_row.get("min_cells_s", 3)),
                    max_cells_s=int(clean_row.get("max_cells_s", 6)),
                    mass_g=float(clean_row.get("mass_g", 25.0)),
                )
            elif ctype == "battery":
                spec = BatterySpec(
                    name=clean_row["name"],
                    cell_count_s=int(clean_row["cell_count_s"]),
                    nominal_voltage_v=float(clean_row["nominal_voltage_v"]),
                    operating_voltage_v=float(clean_row.get("operating_voltage_v", clean_row["nominal_voltage_v"])),
                    capacity_mah=float(clean_row["capacity_mah"]),
                    continuous_c_rating=float(clean_row["continuous_c_rating"]),
                    burst_c_rating=float(clean_row.get("burst_c_rating", float(clean_row["continuous_c_rating"]) * 1.5)),
                    usable_capacity_fraction=float(clean_row.get("usable_capacity_fraction", 0.80)),
                    internal_resistance_per_cell_mohm=float(clean_row.get("internal_resistance_per_cell_mohm", 4.0)),
                    mass_g=float(clean_row.get("mass_g", 500.0)),
                )
            else:
                raise ValueError(f"Unknown component type '{ctype}' for CSV import.")

            self.save_component(ctype, spec, provenance=provenance, source_reference=source_reference)
            imported += 1

        return imported

    def export_components_csv(self, component_type: str) -> str:
        """Export components of a given type as a CSV string."""
        components = self.list_components(component_type)
        if not components:
            return ""
        all_keys = set()
        for c in components:
            all_keys.update(c["spec"].keys())
        fieldnames = ["component_id", "name", "manufacturer", "provenance", "source_reference"] + sorted(list(all_keys))

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for c in components:
            row = {
                "component_id": c["component_id"],
                "name": c["name"],
                "manufacturer": c["manufacturer"],
                "provenance": c["provenance"],
                "source_reference": c["source_reference"],
            }
            row.update(c["spec"])
            writer.writerow(row)
        return output.getvalue()
