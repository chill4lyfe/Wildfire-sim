"""Deterministic placement policies with tier affinity, dynamic queuing, and capacity scoring."""
from __future__ import annotations
from .models import Node, Task


class GreedyLatencyScheduler:
    name = "Greedy Latency-First (Baseline)"

    def choose_node(self, task: Task, nodes: dict[str, Node]) -> tuple[Node | None, str]:
        """Greedily chooses node with the lowest current effective latency."""
        eligible = [n for n in nodes.values() if n.can_fit(task.cpu, task.ram)]
        if not eligible:
            return None, "REJECTED: Cluster capacity exhausted"
        # Sort by dynamic effective latency (including queuing delay)
        best_node = min(eligible, key=lambda n: n.latency_ms)
        return best_node, f"Greedy lowest effective latency ({best_node.latency_ms:.1f}ms)"


class CapacityAwareScheduler:
    name = "Priority-Tiered & Capacity-Aware (Optimized)"

    # Strict operational tiers
    TIER_PREFERENCE = {
        "HIGH": ["EDGE", "FOG", "CLOUD"],
        "MEDIUM": ["FOG", "CLOUD", "EDGE"],
        "LOW": ["CLOUD", "FOG"],  # Hard restriction: LOW tasks cannot run on battery-constrained Edge
    }

    def score(self, node: Node) -> float:
        """Calculates placement penalty based on queuing delay and CPU saturation."""
        load_penalty = 1.0 + 2.5 * ((node.used_cpu / node.total_cpu) ** 2)
        return float(node.latency_ms * load_penalty)

    def choose_node(self, task: Task, nodes: dict[str, Node]) -> tuple[Node | None, str]:
        allowed_tiers = self.TIER_PREFERENCE.get(task.latency_sensitivity, ["CLOUD", "FOG"])
        primary_tier = allowed_tiers[0]

        # 1. Evaluate primary preferred tier
        primary_candidates = [n for n in nodes.values() if n.tier == primary_tier and n.can_fit(task.cpu, task.ram)]
        if primary_candidates:
            # Check for thermal throttle or extreme load
            best_node = min(primary_candidates, key=self.score)
            if best_node.cpu_load_pct < 85.0 and best_node.temperature_c < 80.0:
                return best_node, f"Primary tier match [{primary_tier}] (Load {best_node.cpu_load_pct:.0f}%)"

        # 2. Dynamic failover to secondary allowed tiers
        for fallback_tier in allowed_tiers[1:]:
            fallback_candidates = [n for n in nodes.values() if n.tier == fallback_tier and n.can_fit(task.cpu, task.ram)]
            if fallback_candidates:
                best_node = min(fallback_candidates, key=self.score)
                return best_node, f"Dynamic failover: {primary_tier} -> [{fallback_tier}] (Capacity/Thermal Preserved)"

        return None, "REJECTED: No compliant tier has available CPU/RAM"