<div align="center">

# Wildfire Tactical Incident Command
### Distributed Edge, Fog & Cloud Workload Simulator

*A deterministic, physics-based multi-tier resource scheduler & RBAC simulator built for ARM 305.*

<br/>

<!-- Tech Stack Badges -->
<img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/Streamlit-App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
<img src="https://img.shields.io/badge/Plotly-Interactive-3F4F75?style=for-the-badge&logo=plotly&logoColor=white" alt="Plotly" />
<img src="https://img.shields.io/badge/Pandas-Data-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas" />
<img src="https://img.shields.io/badge/Matplotlib-Charts-11557C?style=for-the-badge" alt="Matplotlib" />

<br/><br/>

[Quick Start](#-quick-start) • [How It Works](#-how-it-works) • [Mandatory Experiments](#-mandatory-experiments) • [Project Layout](#-project-layout)

</div>

---

## Overview

During active forest fires, relying purely on the Cloud is too slow for split-second safety alerts, while relying purely on Edge drones burns battery and overheats processors.

This project simulates a **3-tier joint incident command cluster** that intelligently schedules emergency tasks across:
- 🚁 **Edge Drone Swarm:** 4 vCPU, 8 GB RAM, 8 ms delay (Jetson Orin leader drone).
- 🚒 **Command Truck Fog:** 16 vCPU, 32 GB RAM, 35 ms delay (Local 5G / Starlink on-site server).
- 🏢 **Central Cloud Datacenter:** 64 vCPU, 256 GB RAM, 130 ms delay (NIFC Datacenter).

Everything runs **100% locally** in Python without needing paid cloud accounts, Docker, or real hypervisors.

---

## System Architecture

<div align="center">
  <img width="1224" height="1285" alt="CDEF_project_flowchart" src="https://github.com/user-attachments/assets/d5c2fd15-0f92-4a30-bbb3-e51b7d1c41af" />

</div>

---

## Key Features

- **⚡ Dynamic Queuing Physics ($M/M/1$):** Latency isn't static. As nodes hit peak CPU load, queuing backlog spikes realistically.
- **Drone Battery & Thermal Model:** Running heavy compute on the Edge drone drains battery percentage and spikes core temperature ($^\circ\text{C}$).
- **Dual Placement Policies:**
  - `Greedy Latency-First (Baseline):` Packs the closest node first (chokes the Edge with batch jobs).
  - `Priority-Tiered & Capacity-Aware (Optimized):` Protects Edge battery for urgent safety alerts and delegates batch work to Cloud.
- **Multi-Tenant RBAC:**
  - 3 Agencies: `CAL_FIRE`, `RED_CROSS`, and `USFS_FORESTRY`.
  - Scoped UI views, cross-tenant operation blocks (`403 Forbidden`), and **SHA-256 state hashing** to cryptographically prove zero unauthorized state mutation.
- **Dark-Ops Streamlit HUD:** Includes a 3-stage interactive Sankey flow ribbon, IEEE radar trade-off charts, live node meters, and an audit console.

---

## Quick Start

### 1. Clone & Set Up Environment
```bash
# Navigate to project
cd wildfire_simulator

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies (free & open source only)
pip install -r requirements.txt
```

### 2. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser to view the live tactical dashboard.

### 3. Run Headless Experiments (Generates CSVs & PNGs)
```bash
python experiments/run_experiments.py
```
All experimental results, summary tables, and 300-DPI charts are auto-saved to `experiment_results/`.

---

## Mandatory Experiments (Rubric Verified)

| # | Experiment | Setup | Observed Result | Evidence Output |
|---|---|---|---|---|
| **1** | **Policy Benchmark** | All 12 tasks submitted to Baseline vs. Optimized. | Baseline exhausts Edge CPU; Optimized preserves battery & hits 100% SLA compliance. | `policy_comparison.csv` & `policy_comparison.png` |
| **2** | **Edge Overload** | 5 high-priority tasks (6.0 vCPU) hit 4.0 vCPU Edge node. | First 3 fit on Edge; 4th and 5th gracefully cascade to Fog. Zero dropped tasks. | `edge_overload.csv` |
| **3** | **Security Breach** | `RED_CROSS` attempts unauthorized `STOP_VM` on a `CAL_FIRE` VM. | Immediate `403 FORBIDDEN` denial. SHA-256 hash confirms VM state stayed untouched. | `security_breach.csv` & `security_audit.jsonl` |
| **4** | **Link Degradation** | Command truck latency spikes from 35 ms to 350 ms. | Scheduler calculates mathematical crossover point and migrates medium tasks to Cloud. | `network_degradation.csv` & `fog_degradation.png` |

---

## Project Layout

```text
wildfire_simulator/
├── app.py                      # Interactive Dark-Ops Streamlit Dashboard
├── requirements.txt            # streamlit, pandas, plotly, matplotlib, numpy
├── security_audit.jsonl        # Immutable append-only RBAC security log
├── simulator/
│   ├── models.py               # Node, Task, VM dataclasses & queuing physics
│   ├── scheduler.py            # Greedy Baseline & Capacity-Aware Algorithms
│   ├── security.py             # Tenant authorization & SHA-256 hashing
│   └── engine.py               # Lifecycle engine, SLA tracking & metrics
├── experiments/
│   └── run_experiments.py      # Reproducibility script (exports CSVs & plots)
├── experiment_results/         # Auto-generated CSVs and publication charts
├── assets/
│   └── architecture.png        # Architecture flowchart
└── deliverables/
    ├── ARCHITECTURE.md         # Comprehensive viva defence & spoken script
    ├── REPORT_DRAFT.md         # 5–8 page report draft
    └── PRESENTATION_SLIDES.md  # 6-slide presentation deck
```

---

## Course & Submission Info

- **Course:** ARM 305 — Cloud, Edge, and Fog Computing
- **Project:** Mini Project (Wildfire Telemetry Simulator)
- **Submission:** Complete Runnable ZIP Package (Source, Results, Architecture, Report, Presentation)

---

### The project is made under the GNU GPL-3.0 [LICENSE](LICENSE).
