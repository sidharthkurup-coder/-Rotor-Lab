"""SQLite persistence repository for RotorLab configurations and custom performance datasets."""

from __future__ import annotations

import dataclasses
import json
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
