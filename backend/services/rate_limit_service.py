import ipaddress
import math
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from typing import Deque

from fastapi import Request


class InMemoryRateLimiter:
    """Thread-safe sliding-window limits for a single application process."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self._clock = clock
        self._max_keys = max_keys
        self._lock = threading.Lock()
        self._attempts: OrderedDict[str, Deque[float]] = OrderedDict()

    def consume(self, key: str, limit: int, window_seconds: int) -> int | None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate limit and window must be positive.")

        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                attempts = deque()
                self._attempts[key] = attempts
            else:
                while attempts and attempts[0] <= cutoff:
                    attempts.popleft()

            self._attempts.move_to_end(key)
            if len(attempts) >= limit:
                return max(1, math.ceil(window_seconds - (now - attempts[0])))

            attempts.append(now)
            self._prune_stale()
            while len(self._attempts) > self._max_keys:
                self._attempts.popitem(last=False)
            return None

    def remaining_delay(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                return None
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if not attempts:
                self._attempts.pop(key, None)
                return None
            self._attempts.move_to_end(key)
            if len(attempts) < limit:
                return None
            return max(1, math.ceil(window_seconds - (now - attempts[0])))

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()

    def _prune_stale(self) -> None:
        if len(self._attempts) < 128:
            return
        stale_keys = [
            key
            for key, attempts in self._attempts.items()
            if not attempts
        ]
        for key in stale_keys:
            self._attempts.pop(key, None)


rate_limiter = InMemoryRateLimiter()


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _is_trusted_proxy(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    trusted_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    return any(
        address.version == network.version and address in network
        for network in trusted_networks
    )


def get_client_ip(request: Request, trusted_proxy_ips: list[str]) -> str:
    peer = request.client.host if request.client else "unknown"
    peer_address = _parse_ip(peer)
    if peer_address is None or not trusted_proxy_ips:
        return peer

    trusted_networks = [
        ipaddress.ip_network(value, strict=False) for value in trusted_proxy_ips
    ]
    if not _is_trusted_proxy(peer_address, trusted_networks):
        return peer_address.compressed

    forwarded_for = request.headers.get("x-forwarded-for", "")
    forwarded_addresses = [_parse_ip(value) for value in forwarded_for.split(",")]
    if not forwarded_for or any(address is None for address in forwarded_addresses):
        return peer_address.compressed

    for address in reversed(forwarded_addresses):
        if address is not None and not _is_trusted_proxy(address, trusted_networks):
            return address.compressed
    return forwarded_addresses[0].compressed
