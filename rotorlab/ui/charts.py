"""Module G — Engineering Visualisation using Plotly.

Every chart includes:
- Appropriate axis labels with explicit SI / engineering measurement units.
- Legend where relevant.
- Data-source & provenance footer annotation.
- Relevant engineering assumptions & operating markers (Hover Equilibrium, Operating Point, Component Limits).
"""

from __future__ import annotations

from typing import List

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from rotorlab.services.analyzer import ComparisonRow, CompleteConfigurationAnalysis

# Aerospace dark palette
BG_COLOR = "#0F172A"
PLOT_BG_COLOR = "#111827"
GRID_COLOR = "#1E293B"
TEXT_COLOR = "#F8FAFC"
MUTED_TEXT = "#94A3B8"
CYAN = "#38BDF8"
EMERALD = "#10B981"
AMBER = "#F59E0B"
ROSE = "#F43F5E"
VIOLET = "#A855F7"


def _apply_aerospace_layout(
    fig: go.Figure,
    title: str,
    subtitle_provenance: str,
    xaxis_title: str,
    yaxis_title: str,
    height: int = 410,
) -> go.Figure:
    """Apply consistent dark-themed aerospace engineering styling with provenance footer."""
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:11px;color:{MUTED_TEXT}'>{subtitle_provenance}</span>",
            x=0.01,
            xanchor="left",
            font=dict(size=15, color=TEXT_COLOR),
        ),
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PLOT_BG_COLOR,
        font=dict(family="Inter, Segoe UI, sans-serif", color=TEXT_COLOR, size=12),
        xaxis=dict(
            title=xaxis_title,
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            tickfont=dict(color=MUTED_TEXT),
        ),
        yaxis=dict(
            title=yaxis_title,
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            tickfont=dict(color=MUTED_TEXT),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(15, 23, 42, 0.7)",
            bordercolor=GRID_COLOR,
            borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=55, r=35, t=75, b=55),
        height=height,
        hovermode="x unified",
    )
    return fig


def build_thrust_vs_throttle_chart(analysis: CompleteConfigurationAnalysis) -> go.Figure:
    """Chart 1: Thrust (Single-Motor & Total) vs. Throttle [%] with Hover & Weight Reference."""
    cfg = analysis.config
    ds = analysis.dataset
    tr = analysis.thrust
    num_m = cfg.airframe.num_motors

    throttles = [s.throttle_pct for s in analysis.throttle_curve_states]
    single_gf = [s.thrust_gf for s in analysis.throttle_curve_states]
    total_gf = [num_m * s.thrust_gf for s in analysis.throttle_curve_states]

    raw_th = [p.throttle_pct for p in ds.points]
    raw_single_gf = [p.thrust_gf for p in ds.points]
    raw_total_gf = [num_m * p.thrust_gf for p in ds.points]

    fig = go.Figure()

    # Interpolated Total Thrust Curve
    fig.add_trace(
        go.Scatter(
            x=throttles,
            y=total_gf,
            mode="lines",
            name=f"Total Thrust ({num_m} Motors) [gf]",
            line=dict(color=CYAN, width=3),
            hovertemplate="Total: %{y:.0f} gf<extra></extra>",
        )
    )

    # Measured Raw Data Points (Total)
    fig.add_trace(
        go.Scatter(
            x=raw_th,
            y=raw_total_gf,
            mode="markers",
            name=f"Dataset Points ({ds.provenance.value})",
            marker=dict(color=CYAN, size=8, symbol="diamond", line=dict(width=1.5, color="#FFFFFF")),
            hovertemplate="Measured Total: %{y:.0f} gf<extra></extra>",
        )
    )

    # Single Motor Thrust Curve
    fig.add_trace(
        go.Scatter(
            x=throttles,
            y=single_gf,
            mode="lines+markers",
            name="Single Motor Thrust [gf]",
            line=dict(color=EMERALD, width=2, dash="dot"),
            marker=dict(size=5, color=EMERALD),
            hovertemplate="Single Motor: %{y:.0f} gf<extra></extra>",
        )
    )

    # Aircraft Total Weight Reference Line
    fig.add_hline(
        y=tr.aircraft_weight_gf,
        line_dash="dash",
        line_color=AMBER,
        annotation_text=f"Aircraft Weight: {tr.aircraft_weight_gf:.0f} gf ({tr.aircraft_weight_n:.1f} N)",
        annotation_position="top left",
        annotation_font_color=AMBER,
    )

    # Hover Equilibrium Marker
    if tr.hover_feasible and tr.hover_single_motor_state is not None:
        h_th = tr.hover_single_motor_state.throttle_pct
        fig.add_trace(
            go.Scatter(
                x=[h_th],
                y=[tr.aircraft_weight_gf],
                mode="markers",
                name=f"Hover Equilibrium ({h_th:.1f}%)",
                marker=dict(color=AMBER, size=12, symbol="star", line=dict(width=1.5, color="#FFFFFF")),
                hovertemplate=f"Hover @ {h_th:.1f}% Throttle ({tr.aircraft_weight_gf:.0f} gf)<extra></extra>",
            )
        )

    subtitle = (
        f"Source: {ds.source_reference} | Provenance: {ds.provenance.value} | "
        f"Assumptions: Static sea-level/ISA bench interpolation, {num_m}x {cfg.propeller.code}\" props"
    )
    return _apply_aerospace_layout(
        fig=fig,
        title="Propulsion Thrust vs. Throttle Percentage",
        subtitle_provenance=subtitle,
        xaxis_title="Throttle Command [%]",
        yaxis_title="Static Thrust Force [gf]",
    )


def build_current_vs_throttle_chart(analysis: CompleteConfigurationAnalysis) -> go.Figure:
    """Chart 2: Electrical Current vs. Throttle [%] with Motor & ESC Continuous Limits."""
    cfg = analysis.config
    ds = analysis.dataset
    num_m = cfg.airframe.num_motors
    av_i = cfg.airframe.avionics_power_w / cfg.battery.operating_voltage_v

    throttles = [s.throttle_pct for s in analysis.throttle_curve_states]
    single_i = [s.current_a for s in analysis.throttle_curve_states]
    total_sys_i = [num_m * s.current_a + av_i for s in analysis.throttle_curve_states]

    raw_th = [p.throttle_pct for p in ds.points]
    raw_single_i = [p.current_a for p in ds.points]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=throttles,
            y=total_sys_i,
            mode="lines",
            name=f"Total System Current ({num_m} Motors + Avionics) [A]",
            line=dict(color=VIOLET, width=3),
            hovertemplate="System Current: %{y:.2f} A<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=throttles,
            y=single_i,
            mode="lines",
            name="Single Motor Current [A]",
            line=dict(color=CYAN, width=2.5),
            hovertemplate="Per-Motor Current: %{y:.2f} A<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=raw_th,
            y=raw_single_i,
            mode="markers",
            name="Measured Motor Current [A]",
            marker=dict(color=CYAN, size=8, symbol="circle", line=dict(width=1.5, color="#FFFFFF")),
            hovertemplate="Dataset Point: %{y:.2f} A<extra></extra>",
        )
    )

    # Motor Max Continuous Current Limit
    fig.add_hline(
        y=cfg.motor.max_continuous_current_a,
        line_dash="dash",
        line_color=ROSE,
        annotation_text=f"Motor Max Cont Limit ({cfg.motor.max_continuous_current_a:.1f} A)",
        annotation_position="top left",
        annotation_font_color=ROSE,
    )

    # ESC Continuous Current Rating
    fig.add_hline(
        y=cfg.esc.continuous_current_a,
        line_dash="dot",
        line_color=EMERALD,
        annotation_text=f"ESC Cont Rating ({cfg.esc.continuous_current_a:.1f} A)",
        annotation_position="bottom right",
        annotation_font_color=EMERALD,
    )

    subtitle = (
        f"Source: {ds.source_reference} | Provenance: {ds.provenance.value} | "
        f"Includes {av_i:.2f} A ({cfg.airframe.avionics_power_w:.1f} W) auxiliary avionics draw"
    )
    return _apply_aerospace_layout(
        fig=fig,
        title="Electrical Current Draw vs. Throttle Percentage",
        subtitle_provenance=subtitle,
        xaxis_title="Throttle Command [%]",
        yaxis_title="Electrical Current [A]",
    )


def build_power_vs_throttle_chart(analysis: CompleteConfigurationAnalysis) -> go.Figure:
    """Chart 3: Electrical Input Power [W] & Propulsive Specific Thrust [gf/W] vs. Throttle [%]."""
    cfg = analysis.config
    ds = analysis.dataset
    num_m = cfg.airframe.num_motors

    throttles = [s.throttle_pct for s in analysis.throttle_curve_states]
    single_p = [s.power_w for s in analysis.throttle_curve_states]
    total_p = [
        num_m * s.power_w + cfg.airframe.avionics_power_w
        for s in analysis.throttle_curve_states
    ]
    eff_gf_w = [s.efficiency_gf_w for s in analysis.throttle_curve_states]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=throttles,
            y=total_p,
            mode="lines",
            name="Total Electrical Power [W]",
            line=dict(color=AMBER, width=3),
            hovertemplate="Total Power: %{y:.1f} W<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=throttles,
            y=single_p,
            mode="lines",
            name="Single Motor Power [W]",
            line=dict(color=CYAN, width=2, dash="dash"),
            hovertemplate="Per-Motor Power: %{y:.1f} W<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=throttles,
            y=eff_gf_w,
            mode="lines+markers",
            name="Propulsive Efficacy [gf/W]",
            line=dict(color=EMERALD, width=2),
            marker=dict(size=5, color=EMERALD),
            hovertemplate="Efficacy: %{y:.2f} gf/W<extra></extra>",
        ),
        secondary_y=True,
    )

    subtitle = (
        f"Source: {ds.source_reference} | Provenance: {ds.provenance.value} | "
        f"Bus Voltage: {cfg.battery.operating_voltage_v:.1f} V | Avionics: {cfg.airframe.avionics_power_w:.1f} W"
    )
    _apply_aerospace_layout(
        fig=fig,
        title="Electrical Power Consumption & Propulsive Efficacy vs. Throttle",
        subtitle_provenance=subtitle,
        xaxis_title="Throttle Command [%]",
        yaxis_title="Electrical Power [W]",
    )
    fig.update_yaxes(
        title_text="Specific Thrust Efficacy [gf/W]",
        secondary_y=True,
        gridcolor="rgba(0,0,0,0)",
        tickfont=dict(color=EMERALD),
    )
    return fig


def build_battery_utilisation_chart(analysis: CompleteConfigurationAnalysis) -> go.Figure:
    """Chart 4: Battery C-Rate Utilisation & Flight Endurance across Flight Regimes."""
    el = analysis.electrical
    cfg = analysis.config

    regimes = []
    currents = []
    utilizations = []
    endurances = []
    colors = []

    if el.hover_state is not None:
        regimes.append("Hover Equilibrium")
        currents.append(el.hover_state.total_system_current_a)
        utilizations.append(el.hover_state.battery_continuous_utilization_pct)
        endurances.append(el.hover_state.estimated_endurance_min)
        colors.append(EMERALD)

    regimes.append(f"Operating ({cfg.airframe.operating_throttle_pct:.0f}% Th)")
    currents.append(el.operating_state.total_system_current_a)
    utilizations.append(el.operating_state.battery_continuous_utilization_pct)
    endurances.append(el.operating_state.estimated_endurance_min)
    colors.append(CYAN)

    regimes.append(f"Peak ({analysis.thrust.max_single_motor_state.throttle_pct:.0f}% Th)")
    currents.append(el.peak_state.total_system_current_a)
    utilizations.append(el.peak_state.battery_continuous_utilization_pct)
    endurances.append(el.peak_state.estimated_endurance_min)
    colors.append(ROSE)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=regimes,
            y=utilizations,
            name="Continuous Discharge Utilisation [%]",
            marker_color=colors,
            opacity=0.85,
            text=[f"{u:.1f}% ({c:.1f} A)" for u, c in zip(utilizations, currents)],
            textposition="auto",
            hovertemplate="%{x}: %{y:.1f}% of Continuous C-Limit<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=regimes,
            y=endurances,
            mode="lines+markers+text",
            name="Estimated Flight Endurance [min]",
            line=dict(color=AMBER, width=3),
            marker=dict(size=10, color=AMBER, symbol="diamond"),
            text=[f"{t:.1f} min" for t in endurances],
            textposition="top center",
            hovertemplate="%{x} Endurance: %{y:.1f} min<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.add_hline(
        y=100.0,
        line_dash="dash",
        line_color=ROSE,
        annotation_text=f"100% Continuous Discharge Limit ({el.max_continuous_discharge_a:.1f} A @ {cfg.battery.continuous_c_rating:g}C)",
        annotation_position="top left",
        annotation_font_color=ROSE,
        secondary_y=False,
    )

    subtitle = (
        f"Battery: {cfg.battery.name} ({cfg.battery.capacity_mah:.0f} mAh, {el.usable_capacity_fraction * 100:.0f}% Usable = "
        f"{el.usable_capacity_ah:.2f} Ah / {el.usable_energy_wh:.1f} Wh) | Provenance: {analysis.dataset.provenance.value}"
    )
    _apply_aerospace_layout(
        fig=fig,
        title="Battery Discharge Utilisation & Flight Endurance by Regime",
        subtitle_provenance=subtitle,
        xaxis_title="Flight Operating Regime",
        yaxis_title="Battery Continuous Current Utilisation [%]",
    )
    fig.update_yaxes(
        title_text="Estimated Endurance [minutes]",
        secondary_y=True,
        gridcolor="rgba(0,0,0,0)",
        tickfont=dict(color=AMBER),
    )
    return fig


def build_payload_tradeoff_chart(analysis: CompleteConfigurationAnalysis) -> go.Figure:
    """Chart 5 (Differentiating Feature): Parametric Payload Mass vs. Hover Endurance & Max TWR."""
    sweep = analysis.payload_sweep
    cfg = analysis.config

    pl_kg = [pt.payload_mass_kg for pt in sweep if pt.hover_feasible]
    end_min = [pt.hover_endurance_min for pt in sweep if pt.hover_feasible]
    twr_vals = [pt.twr_max for pt in sweep if pt.hover_feasible]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=pl_kg,
            y=end_min,
            mode="lines+markers",
            name="Hover Endurance [min]",
            line=dict(color=EMERALD, width=3),
            marker=dict(size=6, color=EMERALD),
            hovertemplate="Hover Endurance: %{y:.1f} min<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=pl_kg,
            y=twr_vals,
            mode="lines",
            name="Maximum TWR [-]",
            line=dict(color=CYAN, width=2.5, dash="dash"),
            hovertemplate="Max TWR: %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )

    # Current Payload Marker
    fig.add_vline(
        x=cfg.airframe.payload_mass_kg,
        line_dash="dot",
        line_color=AMBER,
        annotation_text=f"Configured Payload ({cfg.airframe.payload_mass_kg:.2f} kg)",
        annotation_position="top right",
        annotation_font_color=AMBER,
    )

    # Recommended Agile TWR Horizontal Threshold on secondary axis
    fig.add_hline(
        y=cfg.margins.recommended_agile_twr,
        line_dash="dot",
        line_color=ROSE,
        annotation_text=f"Target Design TWR ({cfg.margins.recommended_agile_twr:.2f})",
        annotation_position="bottom left",
        annotation_font_color=ROSE,
        secondary_y=True,
    )

    subtitle = (
        f"Dry Airframe Mass: {cfg.airframe.aircraft_dry_mass_kg:.2f} kg | "
        f"Usable Energy: {analysis.electrical.usable_energy_wh:.1f} Wh | Provenance: {analysis.dataset.provenance.value}"
    )
    _apply_aerospace_layout(
        fig=fig,
        title="Parametric Payload-Endurance & Thrust-to-Weight Tradeoff Envelope",
        subtitle_provenance=subtitle,
        xaxis_title="Mission Payload Mass [kg]",
        yaxis_title="Estimated Hover Endurance [minutes]",
    )
    fig.update_yaxes(
        title_text="Maximum Thrust-to-Weight Ratio (TWR) [-]",
        secondary_y=True,
        gridcolor="rgba(0,0,0,0)",
        tickfont=dict(color=CYAN),
    )
    return fig


def build_configuration_comparison_chart(rows: List[ComparisonRow]) -> go.Figure:
    """Chart 6 (Module F): Multi-Configuration Comparison Bar Chart across Key Performance Metrics."""
    names = [r.config_name for r in rows]
    twrs = [r.twr_max for r in rows]
    hover_end = [r.hover_endurance_min for r in rows]
    op_end = [r.operating_endurance_min for r in rows]
    thrust_kgf = [r.max_total_thrust_gf / 1000.0 for r in rows]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "<b>Max Thrust [kgf] & Max TWR [-]</b>",
            "<b>Hover vs. Operating Endurance [min]</b>",
        ),
        horizontal_spacing=0.12,
    )

    fig.add_trace(
        go.Bar(
            x=names,
            y=thrust_kgf,
            name="Max Total Thrust [kgf]",
            marker_color=CYAN,
            text=[f"{v:.2f} kgf" for v in thrust_kgf],
            textposition="auto",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=names,
            y=twrs,
            name="Max TWR [-]",
            marker_color=VIOLET,
            text=[f"TWR {v:.2f}" for v in twrs],
            textposition="auto",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=names,
            y=hover_end,
            name="Hover Endurance [min]",
            marker_color=EMERALD,
            text=[f"{v:.1f} m" for v in hover_end],
            textposition="auto",
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Bar(
            x=names,
            y=op_end,
            name="Operating Endurance [min]",
            marker_color=AMBER,
            text=[f"{v:.1f} m" for v in op_end],
            textposition="auto",
        ),
        row=1,
        col=2,
    )

    fig.update_layout(
        title=dict(
            text=(
                "<b>Multi-Configuration Propulsion Architecture Comparison</b><br>"
                f"<span style='font-size:11px;color:{MUTED_TEXT}'>"
                "Source: Active configuration datasets | All forces evaluated in SI units (g = 9.80665 m/s²)"
                "</span>"
            ),
            x=0.01,
            font=dict(size=15, color=TEXT_COLOR),
        ),
        barmode="group",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PLOT_BG_COLOR,
        font=dict(family="Inter, Segoe UI, sans-serif", color=TEXT_COLOR, size=11),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(15, 23, 42, 0.7)",
        ),
        margin=dict(l=50, r=30, t=90, b=50),
        height=430,
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, tickfont=dict(color=MUTED_TEXT))
    fig.update_yaxes(gridcolor=GRID_COLOR, tickfont=dict(color=MUTED_TEXT))
    fig.update_yaxes(title_text="Magnitude [kgf / Ratio]", row=1, col=1)
    fig.update_yaxes(title_text="Flight Time [minutes]", row=1, col=2)
    return fig
