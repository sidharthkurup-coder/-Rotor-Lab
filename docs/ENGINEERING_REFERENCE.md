# RotorLab 1.0 — Engineering Reference & Mathematical Formulation

## 1. Fundamental Engineering Philosophy

RotorLab 1.0 is a deterministic propulsion engineering analysis platform for multirotor UAVs. Unlike simplified online calculators that attempt to estimate thrust solely from motor $K_V$ and propeller diameter/pitch using crude empirical constants, RotorLab enforces a strict separation between **empirical thrust-stand performance curves** and **first-principles physical conservation laws**.

### Why Static Thrust Cannot Be Calculated from $K_V$ and Propeller Dimensions Alone
1. **Blade Element Aerodynamics**: Propeller thrust coefficient $C_T$ and power coefficient $C_P$ depend strongly on blade airfoil camber, chord distribution $c(r)$, geometric twist $\beta(r)$, Reynolds number $Re$, tip Mach number, and torsional blade stiffness (e.g., carbon fiber vs. polycarbonate). Two $14 \times 4.8\text{ in}$ propellers from different manufacturers can differ in static thrust and power consumption by $>20\%$ at identical RPM.
2. **Motor Electromagnetic Non-Linearity**: Loaded motor shaft speed $\Omega$ is governed by the balance between aerodynamic torque $Q_{\text{aero}}(\Omega)$ and electromagnetic torque $Q_{\text{em}}(I)$, subject to winding resistance $R_m$, iron eddy-current losses, ESC PWM commutation timing, and battery bus voltage sag.
3. **Data Provenance Policy**: RotorLab therefore interpolates documented motor-propeller performance datasets and tags every curve and operating point with one of four provenance classifications:
   - `Manufacturer Measurements` (verified static bench test tables from T-Motor datasheets)
   - `User-Supplied Measurements` (imported via CSV or entered from a user dynamometer)
   - `Illustrative Synthetic Data` (explicitly labelled synthetic curves for demonstration)
   - `Calculated Estimate` (flagged whenever an operating point requires boundary anchoring or extrapolation outside measured throttle bounds)

---

## 2. Governing Equations & Dimensional Verification

All internal calculations in `rotorlab/engine/` and `rotorlab/models/units.py` execute in consistent SI units ($\text{N}, \text{kg}, \text{m}, \text{s}, \text{V}, \text{A}, \text{W}$) or explicitly defined electrical capacity/energy units ($\text{Ah}, \text{Wh}$).

### 2.1 Gravitational Weight & Force Conversions
Using standard gravitational acceleration $g_0 = 9.80665\text{ m/s}^2$:

$$m_{\text{total}}\,[\text{kg}] = m_{\text{dry}}\,[\text{kg}] + m_{\text{payload}}\,[\text{kg}]$$

$$W_{\text{aircraft}}\,[\text{N}] = m_{\text{total}}\,[\text{kg}] \times g_0\,[\text{m/s}^2]$$

Conversion between gram-force ($\text{gf}$) measured on a load cell and Newtons ($\text{N}$):

$$T\,[\text{N}] = \frac{T\,[\text{gf}]}{1000} \times 9.80665$$

### 2.2 Total Thrust, Hover Equilibrium & Thrust-to-Weight Ratio (TWR)
For an $N$-rotor aircraft with single-motor static thrust $T_{\text{single}}(\theta)$ at throttle percentage $\theta \in [0, 100]$:

$$T_{\text{total}}(\theta)\,[\text{N}] = N \times T_{\text{single}}(\theta)\,[\text{N}]$$

$$\text{TWR}(\theta)\,[-] = \frac{T_{\text{total}}(\theta)\,[\text{N}]}{W_{\text{aircraft}}\,[\text{N}]}$$

**Hover Equilibrium Condition** ($\text{TWR}_{\text{hover}} = 1.0$):

$$T_{\text{hover, single}}\,[\text{N}] = \frac{W_{\text{aircraft}}\,[\text{N}]}{N}$$

RotorLab solves the inverse piecewise-linear interpolation $\theta_{\text{hover}} = T_{\text{single}}^{-1}(T_{\text{hover, single}})$ across the active dataset. If $T_{\text{hover, single}} > T_{\text{single, max}}$, hover is declared **physically infeasible**.

### 2.3 Available Thrust Margin & Payload Margins
- **Available Static Thrust Margin**:
  $$\Delta T_{\text{margin}}\,[\text{N}] = T_{\text{total, max}}\,[\text{N}] - W_{\text{aircraft}}\,[\text{N}]$$
- **Maximum Additional Payload at Target Design TWR ($\text{TWR}_{\text{target}}$)**:
  $$\Delta m_{\text{payload, target}}\,[\text{kg}] = \frac{T_{\text{total, max}}\,[\text{N}]}{\text{TWR}_{\text{target}} \times g_0} - m_{\text{total}}\,[\text{kg}]$$
- **Static Lift Ceiling Payload ($\text{TWR} = 1.0$)**:
  $$m_{\text{payload, max}}\,[\text{kg}] = \max\left(0,\; \frac{T_{\text{total, max}}\,[\text{N}]}{g_0} - m_{\text{dry}}\,[\text{kg}]\right)$$

### 2.4 Actuator Disk Momentum Theory & Rotor Aerodynamics
For a propeller of diameter $D\,[\text{m}] = D\,[\text{in}] \times 0.0254$:
- **Single-Rotor Swept Area**:
  $$A_{\text{disk}}\,[\text{m}^2] = \pi \left(\frac{D}{2}\right)^2$$
- **Rotor Disk Loading**:
  $$DL\,[\text{N/m}^2] = \frac{W_{\text{aircraft}}\,[\text{N}]}{N \cdot A_{\text{disk}}\,[\text{m}^2]}, \qquad DL_{\text{mass}}\,[\text{kg/m}^2] = \frac{m_{\text{total}}\,[\text{kg}]}{N \cdot A_{\text{disk}}\,[\text{m}^2]}$$
- **Hover Induced Velocity ($v_i$) & Ideal Actuator-Disk Power ($P_{\text{ideal}}$)**:
  $$v_i\,[\text{m/s}] = \sqrt{\frac{T_{\text{hover, single}}\,[\text{N}]}{2 \rho A_{\text{disk}}}}, \qquad P_{\text{ideal}}\,[\text{W}] = T_{\text{hover, single}} \cdot v_i = \frac{T_{\text{hover, single}}^{3/2}}{\sqrt{2 \rho A_{\text{disk}}}}$$
- **Overall Electro-Propulsive Figure of Merit ($FM_{\text{sys}}$)**:
  $$FM_{\text{sys}}\,[-] = \frac{P_{\text{ideal}}\,[\text{W}]}{P_{\text{elec, single}}\,[\text{W}]}$$
  where air density $\rho(h, \Delta T)$ is computed from the International Standard Atmosphere (ISA) tropospheric model.

### 2.5 Electrical Power, Battery Energy & Endurance
Given nominal voltage $V_{\text{nom}}\,[\text{V}]$, operating voltage $V_{\text{op}}\,[\text{V}]$, capacity $C\,[\text{Ah}] = C\,[\text{mAh}] / 1000$, and usable capacity fraction $f_{\text{usable}} \in [0.10, 1.00]$:

- **Battery Nominal & Usable Energy**:
  $$E_{\text{nom}}\,[\text{Wh}] = V_{\text{nom}}\,[\text{V}] \times C\,[\text{Ah}], \qquad E_{\text{usable}}\,[\text{Wh}] = f_{\text{usable}} \times E_{\text{nom}}\,[\text{Wh}]$$
- **Total System Current (Motors + Avionics)**:
  $$I_{\text{total}}\,[\text{A}] = N \cdot I_{\text{motor}}\,[\text{A}] + \frac{P_{\text{avionics}}\,[\text{W}]}{V_{\text{op}}\,[\text{V}]}$$
- **Total Electrical Power**:
  $$P_{\text{total}}\,[\text{W}] = V_{\text{op}}\,[\text{V}] \times I_{\text{total}}\,[\text{A}]$$
- **Estimated Flight Endurance**:
  $$t_{\text{endurance}}\,[\text{min}] = \frac{C_{\text{usable}}\,[\text{Ah}]}{I_{\text{total}}\,[\text{A}]} \times 60$$
- **Ohmic Voltage Sag & Motor Copper Loss**:
  $$\Delta V_{\text{sag}}\,[\text{V}] = I_{\text{total}} \cdot (N_{\text{cells}} \cdot R_{\text{cell}}), \qquad P_{\text{Cu, motor}}\,[\text{W}] = I_{\text{motor}}^2 \cdot R_{\text{motor}}$$

---

## 3. Known Limitations & Engineering Assumptions
1. **Static vs. Forward-Flight Inflow**: Bench test datasets measure static thrust ($V_\infty = 0$). In translational forward flight, advance ratio $J = V_\infty / (n D)$ alters blade angle of attack and reduces induced power at moderate cruise speeds while increasing parasitic airframe drag.
2. **Coaxial Rotor Interference**: For coaxial configurations (e.g., Y6, X8 Coax), the lower rotor operates in the contracted slipstream of the upper rotor, typically incurring a $10\text{--}18\%$ static thrust loss relative to isolated rotors.
3. **Dynamic Battery Discharge**: Constant-current endurance equations provide a deterministic baseline; actual flight endurance is influenced by non-linear LiPo discharge curves, Peukert capacity loss at high C-rates, and ambient temperature.
