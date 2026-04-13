"""Sync service — export org to backend native formats."""

from __future__ import annotations

from agentorg.ports.backend import Backend, BackendInfo


class SyncService:
    def __init__(self, backends: dict[str, Backend]) -> None:
        self._backends = backends

    def list_backends(self) -> list[BackendInfo]:
        return [b.info() for b in self._backends.values()]

    def sync(self, backend_name: str, team_id: str | None = None) -> int:
        backend = self._backends.get(backend_name)
        if backend is None:
            raise ValueError(
                f"Backend not found: {backend_name}. "
                f"Available: {', '.join(self._backends.keys())}"
            )
        return backend.sync(team_id)

    def sync_all(self, team_id: str | None = None) -> dict[str, int]:
        results = {}
        for name, backend in self._backends.items():
            results[name] = backend.sync(team_id)
        return results

    def get_backend(self, name: str) -> Backend | None:
        return self._backends.get(name)
