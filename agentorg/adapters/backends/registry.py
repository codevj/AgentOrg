"""Backend registry — discovery and loading."""

from __future__ import annotations

from agentorg.ports.backend import Backend, BackendInfo


class BackendRegistry:
    """Manages available backends."""

    def __init__(self) -> None:
        self._backends: dict[str, Backend] = {}

    def register(self, backend: Backend) -> None:
        info = backend.info()
        self._backends[info.name] = backend

    def get(self, name: str) -> Backend | None:
        return self._backends.get(name)

    def list_all(self) -> list[BackendInfo]:
        return [b.info() for b in self._backends.values()]

    def as_dict(self) -> dict[str, Backend]:
        return dict(self._backends)
