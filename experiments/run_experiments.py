"""Run reproducible experiments and export publication-ready plots."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.engine import SimulationEngine, default_tasks
from simulator.models import Task
from simulator.security import AuthorizationError

OUT = ROOT / "experiment_results"


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    
    # 1. Policy Benchmark
    comp_rows, metrics = [], []
    for pol in ("baseline", "optimized"):
        e = SimulationEngine(audit_path=OUT / "security_audit.jsonl")
        rows = e.deploy(policy=pol)
        comp_rows.extend(rows)
        metrics.append({"policy": pol, **e.metrics(rows)})
        
    df_comp = pd.DataFrame(comp_rows)
    df_metrics = pd.DataFrame(metrics)
    
    # 2. Overload
    e_ovr = SimulationEngine(audit_path=OUT / "security_audit.jsonl")
    surge = [Task(f"OVR-{i+1:02d}", f"Surge Task {i+1}", 1.2, 1.0, "HIGH", "CAL_FIRE", deadline_ms=30.0) for i in range(5)]
    df_overload = pd.DataFrame(e_ovr.deploy(surge, "optimized"))
    
    # 3. Security Breach
    e_sec = SimulationEngine(audit_path=OUT / "security_audit.jsonl")
    t1 = e_sec.deploy([default_tasks()[0]], "optimized")[0]
    vm = e_sec.vms[t1["vm_id"]]
    pre_hash = vm.state_hash()
    try:
        e_sec.stop_vm(vm.vm_id, "RED_CROSS")
        denied = False
    except AuthorizationError:
        denied = True
    post_hash = vm.state_hash()
    df_breach = pd.DataFrame([{
        "vm_id": vm.vm_id,
        "owner": vm.tenant_id,
        "attacker": "RED_CROSS",
        "action": "STOP_VM",
        "denied": denied,
        "immutable_verified": (pre_hash == post_hash),
        "pre_hash": pre_hash,
        "post_hash": post_hash,
    }])
    
    # 4. Degradation
    deg_rows = []
    for label, lat in [("Normal Fog (35ms)", 35), ("Degraded Fog (350ms)", 350)]:
        e_deg = SimulationEngine(fog_latency_ms=lat, audit_path=OUT / "security_audit.jsonl")
        for r in e_deg.deploy([t for t in default_tasks() if t.latency_sensitivity == "MEDIUM"], "optimized"):
            deg_rows.append({**r, "condition": label})
    df_deg = pd.DataFrame(deg_rows)

    # Save CSVs
    df_comp.to_csv(OUT / "policy_comparison.csv", index=False)
    df_metrics.to_csv(OUT / "policy_metrics.csv", index=False)
    df_overload.to_csv(OUT / "edge_overload.csv", index=False)
    df_breach.to_csv(OUT / "security_breach.csv", index=False)
    df_deg.to_csv(OUT / "network_degradation.csv", index=False)

    # ---------------- PUBLICATION-GRADE FIGURE 1 ----------------
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 10,
        'axes.edgecolor': '#94A3B8',
        'axes.linewidth': 0.8,
        'grid.color': '#F1F5F9',
        'grid.linestyle': '--'
    })
    
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), facecolor='white')
    palette = ["#F97316", "#0D9488"]
    labels = df_metrics['policy'].str.title()
    
    # Latency
    b1 = axes[0].bar(labels, df_metrics['avg_latency_ms'], color=palette, width=0.45, edgecolor='black', linewidth=0.5)
    axes[0].set_title("Mean Effective Latency", fontweight='bold', pad=10)
    axes[0].set_ylabel("Milliseconds (ms)")
    axes[0].bar_label(b1, fmt='%.1f ms', padding=3, fontweight='semibold')
    
    # SLA Compliance
    b2 = axes[1].bar(labels, df_metrics['sla_compliance_pct'], color=palette, width=0.45, edgecolor='black', linewidth=0.5)
    axes[1].set_title("SLA Deadline Compliance", fontweight='bold', pad=10)
    axes[1].set_ylabel("Success Rate (%)")
    axes[1].set_ylim(0, 115)
    axes[1].bar_label(b2, fmt='%.0f%%', padding=3, fontweight='semibold')
    
    # Battery Remaining
    b3 = axes[2].bar(labels, df_metrics['edge_battery_pct'], color=palette, width=0.45, edgecolor='black', linewidth=0.5)
    axes[2].set_title("Edge Drone Battery Remaining", fontweight='bold', pad=10)
    axes[2].set_ylabel("Battery Level (%)")
    axes[2].set_ylim(0, 115)
    axes[2].bar_label(b3, fmt='%.0f%%', padding=3, fontweight='semibold')
    
    for ax in axes:
        ax.set_facecolor('white')
        ax.grid(axis='y', alpha=0.7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
    fig.suptitle("ARM 305: Workload Placement Policy Benchmark (Physics & SLA)", fontsize=13, fontweight='bold', y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / "policy_comparison.png", dpi=300, bbox_inches='tight')
    plt.close(fig)

    # ---------------- PUBLICATION-GRADE FIGURE 2 ----------------
    fig, ax = plt.subplots(figsize=(7, 4.2), facecolor='white')
    deg_summary = df_deg.groupby(["condition", "tier"]).size().unstack(fill_value=0)
    deg_summary.plot(kind="bar", stacked=True, ax=ax, color=["#0EA5E9", "#14B8A6", "#64748B"], edgecolor='black', linewidth=0.5, width=0.4)
    
    ax.set_title("Dynamic Workload Migration Under Fog Degradation", fontweight='bold', pad=10)
    ax.set_ylabel("Task Count")
    ax.set_xlabel("")
    ax.legend(title="Target Tier", frameon=True, facecolor='#F8FAFC', edgecolor='none')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.7)
    plt.xticks(rotation=0, fontweight='semibold')
    
    fig.tight_layout()
    fig.savefig(OUT / "fog_degradation.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ Successfully exported all CSV tables and IEEE figures to: {OUT}")


if __name__ == "__main__":
    run()