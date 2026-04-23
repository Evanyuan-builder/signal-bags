"""
SignalRoleBackend — scheme `signal`.

Resolves `signal://roles/<role_id>` refs by loading YAMLs from
`specs/roles/*.yaml` inside this Signal project. Mirrors the
`FileRoleBackend` contract but with a stable scheme + a project-relative
root, so specs/signal.yaml can reference roles without hard-coding an
absolute filesystem path.

Register once at process start:

    from core.backends import role_registry
    from signalbags.backends.signal_role_backend import SignalRoleBackend
    role_registry.register(SignalRoleBackend())
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core.backends.role_backend import RoleBackend, RoleBackendError  # evancore
from core.models.agent_harness import RoleDefinition  # evancore


# Project root: <signal-bags>/signalbags/backends/signal_role_backend.py → parents[2] = <signal-bags>
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ROLES_DIR = _PROJECT_ROOT / "specs" / "roles"


class SignalRoleBackend(RoleBackend):
    scheme = "signal"

    def __init__(self, roles_dir: Path | None = None) -> None:
        self._roles_dir = roles_dir or _ROLES_DIR

    def resolve(self, ref: str, version: str = "latest") -> RoleDefinition:
        role_id = self._parse_role_id(ref)
        path = self._roles_dir / f"{role_id}.yaml"
        if not path.exists():
            raise RoleBackendError(
                f"Signal role {role_id!r} not found at {path}. "
                f"Add a YAML file there or fix the ref."
            )
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RoleBackendError(f"Role file {path} must be a YAML mapping.")
        return RoleDefinition(**raw)

    @staticmethod
    def _parse_role_id(ref: str) -> str:
        prefix = "signal://roles/"
        if not ref.startswith(prefix):
            raise RoleBackendError(
                f"SignalRoleBackend got non-matching ref: {ref!r}. "
                f"Expected 'signal://roles/<role_id>'."
            )
        return ref[len(prefix):].strip("/")
