# ROTORLAB 1.0 // AI-Powered UAV Propulsion Engineering Platform

RotorLab is an AI-powered aerospace propulsion analysis, configuration, and trade-study platform for multirotor UAVs. Combining deterministic aerodynamic and electrical solvers with Google Gemini reasoning, RotorLab enables engineers to design, analyze, compare, and optimize multirotor aircraft using both an interactive 5-step engineering workstation and a conversational AI Copilot.

---

## 🌟 Key Capabilities

### 1. 🤖 Google Gemini AI Copilot with Grounded Function Calling
- **Zero Hallucination Engineering**: The AI Copilot uses Google's official `google-genai` Python SDK with native function calling. Every numerical statistic (thrust, TWR, hover throttle %, power, flight endurance, voltage sag, component margins) is computed directly by RotorLab's verified math solvers.
- **Context-Aware Follow-Ups**: Maintains conversation history and active aircraft context across turns.
- **Integrated Tool Execution**: Calls 9 deterministic engineering functions:
  - `run_propulsion_analysis()`: Complete thrust, electrical, and compatibility evaluation.
  - `calculate_thrust_to_weight()`: Static thrust, AUW, TWR, and agility standards.
  - `calculate_hover_throttle()`: Equilibrium hover throttle percentage and per-rotor power.
  - `calculate_battery_endurance()`: Hover and cruise flight times under Peukert and DoD reserve limits.
  - `check_component_compatibility()`: ESC continuous/peak headroom, motor thermal limits, and battery C-rate margins.
  - `compare_aircraft_configurations()`: Multi-UAV parametric comparison matrix.
  - `analyse_motor_failure()`: Degraded static thrust ($N-1$) and aerodynamic attitude controllability.
  - `retrieve_component_specifications()`: Component search across motors, props, ESCs, and batteries.
  - `create_or_modify_aircraft_configuration()`: Assembles, validates, and saves new UAV configurations directly into the database.

### 2. ➕ Dynamic Aircraft Configuration Builder
- **Beyond Fixed Presets**: Predefined configurations (Surveyor, Valkyrie, Atlas, Tactical) serve as optional reference presets.
- **Custom UAV Creation**: Build any multirotor architecture from scratch (Quadcopters $X4$, Hexacopters $X6$, Octocopters $X8$, Coaxial $X8$, or custom configurations).
- Specify custom mass budgets, payload requirements, operating throttle targets, BLDC motor specs, propeller geometries, ESC ratings, and battery packs.
- Full SQLite persistence: Create, edit, duplicate, save, and delete custom configurations.

### 3. 📑 PDF Datasheet Intelligence
- Upload manufacturer specification sheets (PDF or image).
- Gemini multimodal document understanding automatically extracts motor parameters ($KV$, $I_{\max}$, $P_{\max}$, internal resistance, mass), propeller dimensions, ESC limits, and static bench test curves.
- **Human-in-the-Loop Review**: Extracted specifications are presented in an editable review card with confidence ratings (`HIGH`, `MEDIUM`, `LOW`) and ambiguity notes before committing to the database.

### 4. 📦 Dynamic Component Database & Provenance Tracking
- Dedicated inventory catalog for BLDC motors, propellers, ESCs, and flight batteries.
- Strict data provenance tagging: `Manufacturer Measurements`, `User-Supplied Measurements`, `Calculated Estimate`, and `Illustrative Synthetic Data`.
- **Bulk CSV Import & Export**: Import multiple components via CSV with downloadable templates, or export the catalog.

### 5. 🛠️ 5-Step Engineering Workstation (100% Offline Capable)
- **Step 0 — Overview Dashboard**: Executive KPI bar ($TWR$, hover throttle, battery utilization, endurance) and compatibility badge.
- **Step 1 & 2 — Configure Aircraft & Propulsion**: Parametric specification inputs, mass budget, and component selection.
- **Step 3 — Performance Analysis**: Dark-themed Plotly charts for Thrust vs. Throttle, Electrical Power & Efficacy, Current Draw, and Payload Tradeoff Sweeps.
- **Step 4 — Compare Configurations**: Side-by-side trade-study comparison table with CSV export.
- **Step 5 — Generate Engineering Reports**: One-click export of formal PDF engineering dossiers (`fpdf2`), Markdown technical briefs, and raw CSV curves.

---

## 🔑 Google Gemini API Configuration

RotorLab supports three simple ways to supply your Gemini API key:

### Option A: Local `.env` File (Recommended for Local Development)
Create a `.env` file in the project root directory (a template is provided in `.env.example`):
```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### Option B: System Environment Variable
Set the environment variable in your terminal:
```powershell
$env:GEMINI_API_KEY="your_gemini_api_key_here"
```

### Option C: In-App Sidebar or Copilot Card
Enter your API key directly inside the RotorLab user interface. The key is stored in session memory only and is never written to disk or git.

> [!NOTE]
> **Graceful Degradation**: RotorLab remains 100% operational offline without an API key. The entire 5-step Engineering Workspace, custom aircraft builder, chart visualization, and PDF generation work locally without internet access.

---

## 🚀 Quickstart & Local Execution

### One-Click Launch (Windows 11)
Double-click `run_rotorlab.bat` in the project root folder. It initializes the virtual environment on first launch and opens http://localhost:8501 in your browser.

### Manual Setup
1. **Navigate to the project directory**:
   ```powershell
   cd "C:\Users\Sidharth V Kurup\.gemini\antigravity\scratch\RotorLab"
   ```

2. **Activate the virtual environment & install dependencies**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Run the automated test suite**:
   ```powershell
   pytest -v
   ```

4. **Launch the Streamlit Platform**:
   ```powershell
   streamlit run app.py --server.port 8501
   ```
   Open **http://localhost:8501** in your browser.

---

## 📁 Architecture Overview

```text
RotorLab/
├── app.py                              # Streamlit platform entrypoint & view router
├── requirements.txt                    # Python dependencies (google-genai, streamlit, plotly, etc.)
├── .env.example                        # Template for API credentials
├── .gitignore                          # Excludes .env, virtualenvs, and SQLite databases
├── rotorlab/
│   ├── ai/                             # AI Copilot & GenAI integration
│   │   ├── client.py                   # Official google-genai Client & model config
│   │   ├── tools.py                    # 9 deterministic engineering tools for Gemini
│   │   ├── copilot.py                  # Grounded AI Copilot agent loop
│   │   └── datasheet.py                # Gemini multimodal PDF datasheet parser
│   ├── data/
│   │   ├── datasets.py                 # Factory datasets and CSV performance curves
│   │   └── repository.py               # SQLite persistence (aircraft, components, datasets)
│   ├── engine/
│   │   ├── thrust.py                   # Momentum theory, hover equilibrium & actuator disk
│   │   ├── electrical.py               # Battery energy, voltage sag & endurance engine
│   │   └── compatibility.py            # Safety margins, ESC headroom & thermal checks
│   ├── models/
│   │   ├── domain.py                   # Strongly-typed domain models & provenance enums
│   │   └── units.py                    # SI conversions & ISA atmosphere model
│   ├── reporting/
│   │   └── exporter.py                 # PDF dossier, Markdown brief, and CSV generators
│   ├── services/
│   │   └── analyzer.py                 # Multi-config orchestration and sweeps
│   └── ui/
│       ├── builder_view.py             # Custom aircraft configuration builder dialog
│       ├── copilot_view.py             # AI Copilot conversational UI & datasheet review
│       ├── catalog_view.py             # Dynamic component database & CSV bulk tools
│       └── charts.py                   # Plotly interactive engineering visualisations
└── tests/                              # Pytest test suite (32 unit & integration tests)
```

---

## 🧪 Verification & Testing

Every single engineering tool and math routine is covered by automated unit tests:
```powershell
pytest
```
*Current test suite: 32 tests passing across engine calculations, units, models, repository persistence, AI tools, and graceful degradation.*
