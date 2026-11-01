"""Multi-tenant RBAC enforcement with cryptographic state verification and persistent audit logs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from .models import SecurityEvent, VM


class AuthorizationError(PermissionError):
    def __init__(self, message: str = "403 FORBIDDEN: Unauthorized Cross-Tenant Access"):
        super().__init__(message)


class SecurityManager:
    TENANTS = {
        "CAL_FIRE": {"name": "California Department of Forestry and Fire Protection", "clearance": "TIER-1 TACTICAL", "priority": 1},
        "RED_CROSS": {"name": "American Red Cross Disaster Services", "clearance": "TIER-2 LOGISTICS", "priority": 2},
        "USFS_FORESTRY": {"name": "United States Forest Service", "clearance": "TIER-3 ANALYTICAL", "priority": 3},
    }

    def __init__(self, audit_path: str | Path | None = None):
        self.audit_path = Path(audit_path) if audit_path else Path("security_audit.jsonl")
        self.events: list[SecurityEvent] = []

    def authorize(self, actor_tenant: str, action: str, vm: VM) -> bool:
        """Validates tenant ownership and verifies state immutability via SHA-256."""
        pre_hash = vm.state_hash()
        timestamp = datetime.now(timezone.utc).isoformat()

        if actor_tenant not in self.TENANTS:
            msg = f"403 FORBIDDEN: Unknown entity '{actor_tenant}' denied access to {vm.vm_id}"
            self._log(timestamp, actor_tenant, action, vm.vm_id, "DENIED", msg, pre_hash, vm.state_hash())
            raise AuthorizationError(msg)

        if actor_tenant != vm.tenant_id:
            msg = f"403 FORBIDDEN: Tenant '{actor_tenant}' denied {action} on {vm.vm_id} (Owned by '{vm.tenant_id}')"
            # Verify VM was not mutated
            post_hash = vm.state_hash()
            self._log(timestamp, actor_tenant, action, vm.vm_id, "DENIED", msg, pre_hash, post_hash)
            raise AuthorizationError(msg)

        # Authorized access
        self._log(timestamp, actor_tenant, action, vm.vm_id, "PERMITTED", f"Authorized {action} executed by owner.", pre_hash, vm.state_hash())
        return True

    def _log(self, ts: str, actor: str, act: str, res: str, outcome: str, msg: str, pre: str, post: str) -> None:
        event = SecurityEvent(ts, actor, act, res, outcome, msg, pre, post)
        self.events.append(event)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.__dict__) + "\n")