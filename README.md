# ROTORLAB 1.0
**Professional UAV Propulsion Analysis and Configuration Platform**

RotorLab is a deterministic aerospace propulsion configuration, hover equilibrium, electrical power, compatibility, and trade-study workstation for multirotor UAVs. Built in Python with Streamlit, NumPy, Plotly, SQLite, and FPDF2, it translates multirotor propulsion engineering principles into a rigorous, interactive analysis environment.

---

## Key Engineering Capabilities (Modules A–H)

- **Module A — Propulsion Configuration**: Define multirotor topologies (`X4`, `X6`, `X8`, coaxial), BLDC motor ratings, propeller geometry, ESC current/cell ratings, battery packs, avionics loads, and ISA altitude/temperature conditions. Supports unit selection (`kg`/`g`/`lb`, `inch`/`mm`, `mAh`/`Ah`) and full SQLite persistence (Save, Load, Duplicate, Delete).
- **Module B — Empirical Thrust & Aerodynamic Analysis**: Evaluates single-motor and total propulsion thrust, hover equilibrium throttle/current/RPM, rotor disk loading ($\text{kg/m}^2$ and $\text{N/m}^2$), actuator-disk induced velocity ($v_i$), electro-propulsive Figure of Merit ($FM$), and $N-1$ motor-out thrust ratios. Enforces strict data provenance (`Manufacturer Measurements`, `User-Supplied Measurements`, `Illustrative Synthetic Data`, `Calculated Estimate`) and warns on any out-of-bounds extrapolation.
- **Module C — Electrical Power & Endurance Analysis**: Dimensionally consistent calculation of nominal/usable battery energy ($\text{Wh}$), system current draw (motors + avionics), ohmic voltage sag, stator copper loss ($I^2 R$), continuous/burst C-rate utilization, and estimated flight endurance across Hover, Operating, and Peak regimes.
- **Module D — Thrust-to-Weight Analysis**: Evaluates $\text{TWR} = T_{\text{total}}\,[\text{N}] / W_{\text{aircraft}}\,[\text{N}]$ in strict SI units ($g_0 = 9.80665\text{ m/s}^2$), available thrust margin, and payload limits at both target design TWR and static lift ceiling ($\text{TWR} = 1.0$).
- **Module E — Component Compatibility & Safety Margins**: Evaluates ESC continuous current safety factor, motor current/power thermal limits, battery continuous/burst discharge capability, series cell-count ($S$) voltage matching, and dataset parameter alignment with detailed engineering explanations.
- **Module F — Multi-Configuration Trade Study Comparison**: Side-by-side tabular and graphical comparison of saved multirotor configurations with CSV export.
- **Module G — Interactive Engineering Visualisations**: Dark-themed Plotly aerospace charts with explicit units, operating markers, and data-source provenance footers (Thrust vs. Throttle, Current vs. Throttle, Power & Efficacy vs. Throttle, Battery Utilisation & Endurance, and Parametric Payload-Endurance Tradeoff Envelope).
- **Module H — Downloadable Engineering Reports**: Exports complete PDF engineering dossiers (`fpdf2`), Markdown technical reports, and CSV performance curves.

---

## Project Architecture

```text
RotorLab/
├── app.py                              # Streamlit engineering workstation UI
├── requirements.txt                    # Locked Python dependencies
├── rotorlab/
│   ├── models/
│   │   ├── domain.py                   # Validated dataclasses & provenance enums
│   │   └── units.py                    # SI unit conversions & ISA atmosphere model
│   ├── engine/
│   │   ├── thrust.py                   # Thrust interpolation, hover solver & actuator disk
│   │   ├── electrical.py               # Battery energy, power, sag & endurance engine
│   │   └── compatibility.py            # Configurable engineering margin evaluator
│   ├── data/
│   │   ├── datasets.py                 # T-Motor manufacturer & synthetic datasets + CSV parser
│   │   └── repository.py               # SQLite persistence repository
│   ├── services/
│   │   └── analyzer.py                 # Single-config orchestration, sweeps & comparison
│   ├── reporting/
│   │   └── exporter.py                 # PDF, CSV, and Markdown report generators
│   └── ui/
│       └── charts.py                   # Interactive Plotly engineering charts
├── datasets/                           # Sample CSV thrust-stand datasets for import
├── docs/
│   └── ENGINEERING_REFERENCE.md        # Mathematical derivations & limitations
└── tests/                              # Automated Pytest QA suite
```

---

## Quickstart & Local Execution (Windows 11)

**Fastest:** double-click `run_rotorlab.bat` (or run its full path from any terminal). It creates the virtual environment on first use and launches the app at http://localhost:8501.

**Manual steps** (commands must be run from inside the RotorLab folder):

1. **Activate the virtual environment** (or create one if setting up fresh):
   ```powershell
   cd "C:\Users\Sidharth V Kurup\.gemini\antigravity\scratch\RotorLab"
   python -m venv .venv
   .\.venv\Scripts\pip.exe install -r requirements.txt
   ```

2. **Run the automated test suite**:
   ```powershell
   .\.venv\Scripts\pytest.exe -v
   ```

3. **Launch the RotorLab Streamlit Workstation**:
   ```powershell
   .\.venv\Scripts\streamlit.exe run app.py --server.port 8501
   ```
   Open **http://localhost:8501** in your browser.
