"""Nightingale (夜莺) monitoring system client.

Fetches host-level metrics via the Prometheus-compatible query API
that Nightingale exposes at <nightingale_url>/prometheus/api/v1/query.

Authentication uses Nightingale's JWT login endpoint.
"""

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings


@dataclass
class HostMetrics:
    host: str = ""
    collected_at: str = ""
    cpu: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    disk: dict[str, Any] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    load: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)


class NightingaleCollector:
    """Client for fetching host metrics from a Nightingale monitoring server.

    Supports both categraf metric naming (default for Nightingale)
    and node_exporter naming as a fallback.
    """

    # Metric name candidates: categraf first, node_exporter fallback
    _METRICS = {
        "cpu_usage_active":  ["cpu_usage_active",    "node_cpu_seconds_total"],
        "cpu_usage_user":    ["cpu_usage_user",       None],
        "cpu_usage_system":  ["cpu_usage_system",     None],
        "cpu_usage_iowait":  ["cpu_usage_iowait",     None],
        "mem_used_percent":  ["mem_used_percent",     None],
        "mem_total":         ["mem_total",            "node_memory_MemTotal_bytes"],
        "mem_used":          ["mem_used",             None],
        "mem_available":     ["mem_available",        "node_memory_MemAvailable_bytes"],
        "disk_used_percent": ["disk_used_percent",    None],
        "disk_total":        ["disk_total",           "node_filesystem_size_bytes"],
        "disk_used":         ["disk_used",            None],
        "disk_free":         ["disk_free",            "node_filesystem_free_bytes"],
        "net_bytes_recv":    ["net_bytes_recv",       "node_network_receive_bytes_total"],
        "net_bytes_sent":    ["net_bytes_sent",       "node_network_transmit_bytes_total"],
        "net_packets_recv":  ["net_packets_recv",     None],
        "net_packets_sent":  ["net_packets_sent",     None],
        "net_drop_in":       ["net_drop_in",          None],
        "net_drop_out":      ["net_drop_out",         None],
        "load1":             ["system_load1",         "node_load1"],
        "load5":             ["system_load5",         "node_load5"],
        "load15":            ["system_load15",        "node_load15"],
    }

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        prom_path: str | None = None,
        timeout: int = 10,
    ):
        self._base_url = (url or settings.nightingale_url).rstrip("/")
        self._username = username or settings.nightingale_username
        self._password = password or settings.nightingale_password
        self._prom_path = (prom_path or settings.nightingale_prom_path).rstrip("/")
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires: float = 0.0

    # ------------------------------------------------------------------ #
    #  Authentication
    # ------------------------------------------------------------------ #

    def _ensure_token(self) -> None:
        if self._token and time.time() < self._token_expires:
            return
        resp = httpx.post(
            f"{self._base_url}/api/n9e/auth/login",
            json={"username": self._username, "password": self._password},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = (
            data.get("dat", {}).get("access_token")
            or data.get("access_token")
            or data.get("token")
        )
        if not self._token:
            raise RuntimeError(f"Nightingale login failed: {data}")
        self._token_expires = time.time() + 3600  # assume 1-hour TTL

    def _headers(self) -> dict[str, str]:
        self._ensure_token()
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------ #
    #  Prometheus query
    # ------------------------------------------------------------------ #

    def _query(self, promql: str, ts: float | None = None) -> float | None:
        """Execute an instant PromQL query and return the first scalar value."""
        params: dict[str, Any] = {"query": promql}
        if ts:
            params["time"] = ts
        resp = httpx.get(
            f"{self._base_url}{self._prom_path}/api/v1/query",
            params=params,
            headers=self._headers(),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        results = payload.get("data", {}).get("result", [])
        if not results:
            return None
        try:
            return float(results[0]["value"][1])
        except (IndexError, KeyError, ValueError):
            return None

    def _query_metric(self, logical_name: str, host: str, extra_filter: str = "") -> float | None:
        """Try categraf metric name, then node_exporter fallback."""
        candidates = self._METRICS.get(logical_name, [logical_name, None])
        host_filter = f'ident="{host}"' if host else ""

        for metric in candidates:
            if metric is None:
                continue
            filters = ", ".join(f for f in [host_filter, extra_filter] if f)
            promql = f'{metric}{{{filters}}}' if filters else metric
            try:
                val = self._query(promql)
                if val is not None:
                    return val
            except Exception:
                continue
        return None

    def _query_rate(self, metric: str, host: str, window: str = "5m") -> float | None:
        host_filter = f'ident="{host}"' if host else ""
        promql = (
            f'rate({metric}{{{host_filter}}}[{window}])'
            if host_filter
            else f'rate({metric}[{window}])'
        )
        try:
            val = self._query(promql)
            return val
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def collect(self, host: str) -> HostMetrics:
        """Collect all host metrics for the given host identifier."""
        from datetime import datetime, timezone

        result = HostMetrics(
            host=host,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

        def _safe(label: str, fn):
            try:
                return fn()
            except Exception as exc:
                result.errors.append(f"{label}: {exc}")
                return {}

        result.cpu = _safe("cpu", lambda: self._collect_cpu(host))
        result.memory = _safe("memory", lambda: self._collect_memory(host))
        result.disk = _safe("disk", lambda: self._collect_disk(host))
        result.network = _safe("network", lambda: self._collect_network(host))
        result.load = _safe("load", lambda: self._collect_load(host))
        return result

    def _collect_cpu(self, host: str) -> dict:
        def _v(name: str) -> float | None:
            return self._query_metric(name, host)

        usage_active = _v("cpu_usage_active")
        if usage_active is None:
            # node_exporter: derive from idle
            idle_rate = self._query_rate("node_cpu_seconds_total", host)
            usage_active = round((1 - (idle_rate or 0)) * 100, 2) if idle_rate else None

        return {
            "usage_active_pct": usage_active,
            "usage_user_pct": _v("cpu_usage_user"),
            "usage_system_pct": _v("cpu_usage_system"),
            "usage_iowait_pct": _v("cpu_usage_iowait"),
        }

    def _collect_memory(self, host: str) -> dict:
        used_pct = self._query_metric("mem_used_percent", host)
        total = self._query_metric("mem_total", host)
        used = self._query_metric("mem_used", host)
        available = self._query_metric("mem_available", host)

        # Fallback: derive used_pct from total and available
        if used_pct is None and total and available:
            used_pct = round((total - available) / total * 100, 2)

        return {
            "used_pct": used_pct,
            "total_bytes": total,
            "used_bytes": used,
            "available_bytes": available,
        }

    def _collect_disk(self, host: str) -> dict:
        return {
            "used_pct": self._query_metric("disk_used_percent", host),
            "total_bytes": self._query_metric("disk_total", host),
            "used_bytes": self._query_metric("disk_used", host),
            "free_bytes": self._query_metric("disk_free", host),
        }

    def _collect_network(self, host: str) -> dict:
        return {
            "recv_bytes_per_sec": self._query_rate("net_bytes_recv", host),
            "sent_bytes_per_sec": self._query_rate("net_bytes_sent", host),
            "recv_packets_per_sec": self._query_rate("net_packets_recv", host),
            "sent_packets_per_sec": self._query_rate("net_packets_sent", host),
            "drop_in_per_sec": self._query_rate("net_drop_in", host),
            "drop_out_per_sec": self._query_rate("net_drop_out", host),
        }

    def _collect_load(self, host: str) -> dict:
        return {
            "load1": self._query_metric("load1", host),
            "load5": self._query_metric("load5", host),
            "load15": self._query_metric("load15", host),
        }
