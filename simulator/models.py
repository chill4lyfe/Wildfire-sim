"""Core domain models with dynamic queuing physics, thermal, and cryptographic state hashing."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

VMStatus = Literal["PROVISIONING", "RUNNING", "STOPPED", "TERMINATED"]


@dataclass
class Task:
    task_id: str
    name: str
    cpu: float
    ram: float
    latency_sensitivity: Literal["HIGH", "MEDIUM", "LOW"]
    tenant_id: str
    deadline_ms: float = 150.0  # Maximum latency before SLA violation


@dataclass
class Node:
    node_id: str
    name: str
    tier: Literal["EDGE", "FOG", "CLOUD"]
    total_cpu: float
    total_ram: float
    base_latency_ms: float
    used_cpu: float = 0.0
    used_ram: float = 0.0
    battery_pct: float = 100.0       # Edge battery model (%)
    temperature_c: float = 42.0      # Thermal model (Celsius)

    @property
    def free_cpu(self) -> float:
        return max(0.0, self.total_cpu - self.used_cpu)

    @property
    def free_ram(self) -> float:
        return max(0.0, self.total_ram - self.used_ram)

    @property
    def cpu_load_pct(self) -> float:
        return (100.0 * self.used_cpu / self.total_cpu) if self.total_cpu else 0.0

    @property
    def ram_load_pct(self) -> float:
        return (100.0 * self.used_ram / self.total_ram) if self.total_ram else 0.0

    @property
    def latency_ms(self) -> float:
        """Dynamic effective latency incorporating M/M/1 queuing congestion and thermal throttling."""
        rho = min(0.98, self.used_cpu / self.total_cpu if self.total_cpu else 0.0)
        # Queuing delay multiplier: explodes as rho -> 1.0
        queue_multiplier = 1.0 + (rho / (1.02 - rho))
        thermal_penalty = 1.4 if self.temperature_c > 75.0 else 1.0
        return float(self.base_latency_ms * queue_multiplier * thermal_penalty)

    def can_fit(self, cpu: float, ram: float) -> bool:
        return (self.free_cpu + 1e-6 >= cpu) and (self.free_ram + 1e-6 >= ram)

    def reserve(self, cpu: float, ram: float) -> None:
        if not self.can_fit(cpu, ram):
            raise ValueError(f"Insufficient capacity on {self.node_id}")
        self.used_cpu += cpu
        self.used_ram += ram
        # Physics model: Edge nodes heat up and drain battery under load
        if self.tier == "EDGE":
            self.temperature_c = min(95.0, self.temperature_c + (cpu * 4.5))
            self.battery_pct = max(5.0, self.battery_pct - (cpu * 2.2))
        elif self.tier == "FOG":
            self.temperature_c = min(80.0, self.temperature_c + (cpu * 1.5))

    def release(self, cpu: float, ram: float) -> None:
        self.used_cpu = max(0.0, self.used_cpu - cpu)
        self.used_ram = max(0.0, self.used_ram - ram)
        if self.tier == "EDGE":
            self.temperature_c = max(42.0, self.temperature_c - (cpu * 3.5))
        elif self.tier == "FOG":
            self.temperature_c = max(38.0, self.temperature_c - (cpu * 1.0))


@dataclass
class VM:
    vm_id: str
    task_id: str
    tenant_id: str
    host_node: str
    allocated_cpu: float
    allocated_ram: float
    status: VMStatus = "PROVISIONING"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def state_hash(self) -> str:
        """Cryptographic SHA-256 fingerprint to verify zero unauthorized tampering."""
        payload = f"{self.vm_id}|{self.task_id}|{self.tenant_id}|{self.host_node}|{self.allocated_cpu}|{self.allocated_ram}|{self.status}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


@dataclass
class SecurityEvent:
    timestamp: str
    actor_tenant: str
    action: str
    resource_id: str
    outcome: Literal["PERMITTED", "DENIED"]
    message: str
    pre_attack_hash: str = ""
    post_attack_hash: str = ""


def make_nodes(fog_latency_ms: float = 35.0) -> dict[str, Node]:
    return {
        "Edge_Drone_Swarm": Node("Edge_Drone_Swarm", "Edge Drone Leader (Jetson Orin)", "EDGE", total_cpu=4.0, total_ram=8.0, base_latency_ms=8.0, battery_pct=92.0, temperature_c=48.0),
        "Fog_Mobile_Command": Node("Fog_Mobile_Command", "Command Truck Server (Local 5G)", "FOG", total_cpu=16.0, total_ram=32.0, base_latency_ms=fog_latency_ms, battery_pct=100.0, temperature_c=40.0),
        "Cloud_NIFC_Central": Node("Cloud_NIFC_Central", "NIFC GovCloud Datacenter", "CLOUD", total_cpu=64.0, total_ram=256.0, base_latency_ms=130.0, battery_pct=100.0, temperature_c=25.0),
    }