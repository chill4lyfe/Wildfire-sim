"""Execution engine tracking VM lifecycles, SLA compliance, queuing latency, and telemetry."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
from .models import Node, Task, VM, make_nodes
from .scheduler import CapacityAwareScheduler, GreedyLatencyScheduler
from .security import SecurityManager, AuthorizationError


def default_tasks() -> list[Task]:
    return [
        Task("TSK-01", "Thermal Flashover Alert", 0.8, 1.0, "HIGH", "CAL_FIRE", deadline_ms=25.0),
        Task("TSK-02", "Drone Collision Avoidance", 1.2, 1.5, "HIGH", "CAL_FIRE", deadline_ms=20.0),
        Task("TSK-03", "Toxic Gas Spike (CO/HCN)", 0.6, 0.8, "HIGH", "CAL_FIRE", deadline_ms=30.0),
        Task("TSK-04", "Retardant Drop Targeting", 1.4, 1.8, "HIGH", "CAL_FIRE", deadline_ms=35.0),
        Task("TSK-05", "Perimeter IR Map Stitching", 2.5, 3.0, "MEDIUM", "USFS_FORESTRY", deadline_ms=90.0),
        Task("TSK-06", "Evacuation Route Cam Stream", 3.0, 4.0, "MEDIUM", "RED_CROSS", deadline_ms=80.0),
        Task("TSK-07", "Wind Vector Interpolation", 1.5, 1.5, "MEDIUM", "USFS_FORESTRY", deadline_ms=70.0),
        Task("TSK-08", "Crew Vitals & Heat-Stress", 1.0, 1.0, "MEDIUM", "CAL_FIRE", deadline_ms=60.0),
        Task("TSK-09", "Satellite Multi-Spectral Fusion", 10.0, 20.0, "LOW", "USFS_FORESTRY", deadline_ms=300.0),
        Task("TSK-10", "Monte Carlo Fire Spread Sim", 16.0, 32.0, "LOW", "USFS_FORESTRY", deadline_ms=450.0),
        Task("TSK-11", "Incident Blackbox Archival", 4.0, 8.0, "LOW", "CAL_FIRE", deadline_ms=500.0),
        Task("TSK-12", "Burn Severity Index (BARC)", 8.0, 16.0, "LOW", "USFS_FORESTRY", deadline_ms=400.0),
    ]


class SimulationEngine:
    def __init__(self, fog_latency_ms: float = 35.0, audit_path: str | Path | None = None):
        self.nodes: dict[str, Node] = make_nodes(fog_latency_ms)
        self.tasks: dict[str, Task] = {t.task_id: t for t in default_tasks()}
        self.vms: dict[str, VM] = {}
        self.security = SecurityManager(audit_path)
        self.results: list[dict] = []
        self._vm_seq = 0

    def create_vm(self, task: Task, node: Node) -> VM:
        node.reserve(task.cpu, task.ram)
        self._vm_seq += 1
        vm = VM(f"VM-{self._vm_seq:03d}", task.task_id, task.tenant_id, node.node_id, task.cpu, task.ram, "RUNNING")
        self.vms[vm.vm_id] = vm
        return vm

    def stop_vm(self, vm_id: str, actor_tenant: str) -> VM:
        if vm_id not in self.vms:
            raise KeyError(f"VM {vm_id} does not exist.")
        vm = self.vms[vm_id]
        self.security.authorize(actor_tenant, "STOP_VM", vm)
        if vm.status == "RUNNING":
            self.nodes[vm.host_node].release(vm.allocated_cpu, vm.allocated_ram)
            vm.status = "STOPPED"
        return vm

    def terminate_vm(self, vm_id: str, actor_tenant: str) -> VM:
        if vm_id not in self.vms:
            raise KeyError(f"VM {vm_id} does not exist.")
        vm = self.vms[vm_id]
        self.security.authorize(actor_tenant, "TERMINATE_VM", vm)
        if vm.status == "RUNNING":
            self.nodes[vm.host_node].release(vm.allocated_cpu, vm.allocated_ram)
        vm.status = "TERMINATED"
        return vm

    def deploy(self, tasks: list[Task] | None = None, policy: str = "optimized") -> list[dict]:
        scheduler = GreedyLatencyScheduler() if policy == "baseline" else CapacityAwareScheduler()
        rows = []
        task_list = tasks if tasks is not None else list(self.tasks.values())

        for task in task_list:
            node, reason = scheduler.choose_node(task, self.nodes)
            if node is None:
                row = self._record(task, policy, None, False, "REJECTED", 999.0, reason)
            else:
                vm = self.create_vm(task, node)
                effective_lat = node.latency_ms
                row = self._record(task, policy, node, True, vm.vm_id, effective_lat, reason)
            rows.append(row)
            self.results.append(row)
        return rows

    def _record(self, task: Task, policy: str, node: Node | None, success: bool, vm_id: str, lat: float, reason: str) -> dict:
        sla_met = (lat <= task.deadline_ms) if success else False
        return {
            "task_id": task.task_id,
            "task_name": task.name,
            "tenant_id": task.tenant_id,
            "sensitivity": task.latency_sensitivity,
            "cpu": task.cpu,
            "ram_gb": task.ram,
            "deadline_ms": task.deadline_ms,
            "policy": policy,
            "host_node": node.node_id if node else "NONE",
            "tier": node.tier if node else "NONE",
            "latency_ms": round(lat, 1) if success else None,
            "sla_met": sla_met,
            "success": success,
            "vm_id": vm_id,
            "placement_reason": reason,
        }

    def metrics(self, rows: list[dict] | None = None) -> dict:
        df = pd.DataFrame(rows if rows is not None else self.results)
        if df.empty:
            return {"success_rate_pct": 0, "avg_latency_ms": 0, "sla_compliance_pct": 0, "edge_cpu_pct": 0, "edge_battery_pct": 100, "edge_temp_c": 42}
        ok = df[df.success]
        edge = self.nodes["Edge_Drone_Swarm"]
        sla_comp = (df["sla_met"].sum() / len(df) * 100) if len(df) else 0.0
        return {
            "success_rate_pct": round(100.0 * len(ok) / len(df), 1),
            "avg_latency_ms": round(float(ok["latency_ms"].mean()), 1) if len(ok) else 0.0,
            "sla_compliance_pct": round(sla_comp, 1),
            "edge_cpu_pct": round(edge.cpu_load_pct, 1),
            "edge_battery_pct": round(edge.battery_pct, 1),
            "edge_temp_c": round(edge.temperature_c, 1),
            "fog_cpu_pct": round(self.nodes["Fog_Mobile_Command"].cpu_load_pct, 1),
            "cloud_cpu_pct": round(self.nodes["Cloud_NIFC_Central"].cpu_load_pct, 1),
        }