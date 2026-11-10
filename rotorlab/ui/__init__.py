"""RotorLab UI view components and chart builders."""

from rotorlab.ui.builder_view import render_new_aircraft_dialog
from rotorlab.ui.catalog_view import render_catalog_view
from rotorlab.ui.charts import (
    build_battery_utilisation_chart,
    build_configuration_comparison_chart,
    build_current_vs_throttle_chart,
    build_payload_tradeoff_chart,
    build_power_vs_throttle_chart,
    build_thrust_vs_throttle_chart,
)
from rotorlab.ui.copilot_view import render_copilot_view

__all__ = [
    "render_new_aircraft_dialog",
    "render_copilot_view",
    "render_catalog_view",
    "build_thrust_vs_throttle_chart",
    "build_power_vs_throttle_chart",
    "build_current_vs_throttle_chart",
    "build_battery_utilisation_chart",
    "build_payload_tradeoff_chart",
    "build_configuration_comparison_chart",
]
