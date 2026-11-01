import ipaddress
import re
import socket
import ssl
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import SplitResult, quote, urljoin, urlsplit, urlunsplit

import dns.exception
import dns.resolver

from utils.company_utils import extract_domain


CONNECT_TIMEOUT_SECONDS = 1.5
DNS_TIMEOUT_SECONDS = 2.0
MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 64 * 1024
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
SIX_TO_FOUR_PREFIX = ipaddress.ip_network("2002::/16")
TEREDO_PREFIX = ipaddress.ip_network("2001::/32")
METADATA_HOSTS = {
    "metadata",
    "metadata.google.internal",
    "metadata.azure.internal",
    "metadata.tencentyun.com",
    "instance-data",
    "instance-data.ec2.internal",
}
BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".localdomain",
    ".local",
    ".internal",
    ".test",
    ".invalid",
    ".example",
    ".metadata.google.internal",
    ".metadata.azure.internal",
    ".metadata.tencentyun.com",
)


class WebsiteProbeError(ValueError):
    """Raised when a website URL is unsafe or cannot be checked safely."""


def _normalize_url(url: str) -> Tuple[str, SplitResult]:
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise WebsiteProbeError("Invalid website URL")
    if "\\" in url or any(ord(char) <= 0x20 or ord(char) == 0x7F for char in url):
        raise WebsiteProbeError("Invalid website URL")

    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme not in {"http", "https"} or not parts.netloc:
            raise WebsiteProbeError("Unsupported website URL")
        if parts.username is not None or parts.password is not None:
            raise WebsiteProbeError("Website URL credentials are not allowed")

        hostname = parts.hostname
        if not hostname or "%" in hostname or parts.netloc.endswith(":"):
            raise WebsiteProbeError("Invalid website host")
        port = parts.port
    except ValueError as exc:
        raise WebsiteProbeError("Invalid website URL") from exc

    if port == 0:
        raise WebsiteProbeError("Invalid website port")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise WebsiteProbeError("Invalid website host") from exc

        labels = host.split(".")
        if (
            not host
            or len(host) > 253
            or len(labels) < 2
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            )
        ):
            raise WebsiteProbeError("Invalid website host")
        if host in METADATA_HOSTS or any(
            host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES
        ):
            raise WebsiteProbeError("Metadata and local hostnames are not allowed")
        display_host = host
    else:
        _require_public_address(address)
        host = address.compressed
        display_host = f"[{host}]" if address.version == 6 else host

    path = parts.path or "/"
    authority = f"{display_host}:{port}" if port is not None else display_host
    normalized = urlunsplit((scheme, authority, path, parts.query, ""))
    return normalized, parts


def _require_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    elif isinstance(address, ipaddress.IPv6Address):
        numeric_address = int(address)
        if address in NAT64_PREFIX:
            _require_public_address(ipaddress.IPv4Address(numeric_address & 0xFFFFFFFF))
        elif address in SIX_TO_FOUR_PREFIX:
            _require_public_address(ipaddress.IPv4Address((numeric_address >> 80) & 0xFFFFFFFF))
        elif address in TEREDO_PREFIX:
            _require_public_address(ipaddress.IPv4Address((~numeric_address) & 0xFFFFFFFF))
    if (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        raise WebsiteProbeError("Website host resolved to a non-public address")


def _resolve_host_addresses(host: str) -> List[str]:
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT_SECONDS
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    addresses = []
    for record_type in ("A", "AAAA"):
        try:
            answer = resolver.resolve(
                host,
                record_type,
                lifetime=DNS_TIMEOUT_SECONDS,
                search=False,
            )
        except dns.resolver.NoAnswer:
            continue
        addresses.extend(str(record) for record in answer)
    return addresses


def _public_addresses(host: str) -> List[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        _require_public_address(literal)
        return [literal]

    try:
        resolved = _resolve_host_addresses(host)
    except (dns.exception.DNSException, OSError) as exc:
        raise WebsiteProbeError("Website DNS resolution failed") from exc

    if not resolved:
        raise WebsiteProbeError("Website DNS resolution returned no addresses")

    addresses = []
    for value in resolved:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise WebsiteProbeError("Website DNS resolution returned an invalid address") from exc
        _require_public_address(address)
        if address not in addresses:
            addresses.append(address)
    return addresses


def resolve_public_host(
    host: str,
) -> List[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a host and require every answer to be a public address."""
    return _public_addresses(host)


def _connect_to_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address, port: int
) -> socket.socket:
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    connection = socket.socket(family, socket.SOCK_STREAM)
    try:
        connection.settimeout(CONNECT_TIMEOUT_SECONDS)
        if address.version == 6:
            connection.connect((address.compressed, port, 0, 0))
        else:
            connection.connect((address.compressed, port))
        return connection
    except OSError:
        connection.close()
        raise


def _read_head_response(connection: socket.socket) -> Tuple[int, Optional[str]]:
    response = bytearray()
    delimiter = b"\r\n\r\n"
    while delimiter not in response:
        if len(response) >= MAX_RESPONSE_BYTES:
            raise WebsiteProbeError("Website response headers exceed the size limit")
        chunk = connection.recv(min(4096, MAX_RESPONSE_BYTES - len(response)))
        if not chunk:
            raise WebsiteProbeError("Website returned an incomplete response")
        response.extend(chunk)

    header_block = bytes(response).split(delimiter, 1)[0]
    lines = header_block.split(b"\r\n")
    status_match = re.fullmatch(rb"HTTP/1\.[01] ([0-9]{3})(?: .*)?", lines[0])
    if not status_match:
        raise WebsiteProbeError("Website returned an invalid HTTP response")

    location = None
    for line in lines[1:]:
        if not line or line[:1] in (b" ", b"\t") or b":" not in line:
            raise WebsiteProbeError("Website returned invalid HTTP headers")
        name, value = line.split(b":", 1)
        try:
            header_name = name.decode("ascii").lower()
            header_value = value.decode("latin-1").strip()
        except UnicodeDecodeError as exc:
            raise WebsiteProbeError("Website returned invalid HTTP headers") from exc
        if header_name == "location":
            if location is not None:
                raise WebsiteProbeError("Website returned an ambiguous redirect")
            location = header_value
    return int(status_match.group(1)), location


def _send_head_request(
    scheme: str,
    host: str,
    port: int,
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    path: str,
    query: str,
) -> Tuple[int, Optional[str]]:
    connection = None
    try:
        connection = _connect_to_address(address, port)
        if scheme == "https":
            connection = ssl.create_default_context().wrap_socket(
                connection,
                server_hostname=host,
            )

        request_target = quote(
            path or "/", safe="/%:@!$&'()*+,;=-._~"
        )
        if query:
            request_target += "?" + quote(
                query, safe="/?%:@!$&'()*+,;=-._~"
            )
        host_header = f"[{host}]" if ":" in host else host
        if port != (443 if scheme == "https" else 80):
            host_header += f":{port}"
        request = (
            f"HEAD {request_target} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "User-Agent: CareerShield-Audit/1.0\r\n"
            "Accept: */*\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        connection.sendall(request)
        return _read_head_response(connection)
    except WebsiteProbeError:
        raise
    except (OSError, ssl.SSLError, UnicodeError) as exc:
        raise WebsiteProbeError("Website connection failed") from exc
    finally:
        if connection is not None:
            connection.close()


def _probe_website(url: str) -> int:
    candidate = url if url.lower().startswith(("http://", "https://")) else f"https://{url}"
    current_url, _ = _normalize_url(candidate)

    for redirect_count in range(MAX_REDIRECTS + 1):
        current_url, parts = _normalize_url(current_url)
        host = parts.hostname
        if not host:
            raise WebsiteProbeError("Invalid website host")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            host = host.rstrip(".").encode("idna").decode("ascii").lower()
        port = parts.port or (443 if parts.scheme == "https" else 80)
        addresses = _public_addresses(host)
        status, location = _send_head_request(
            parts.scheme,
            host,
            port,
            addresses[0],
            parts.path or "/",
            parts.query,
        )
        if status not in REDIRECT_STATUSES or not location:
            return status
        if redirect_count >= MAX_REDIRECTS:
            raise WebsiteProbeError("Website exceeded the redirect limit")
        current_url = urljoin(current_url, location)

    raise WebsiteProbeError("Website exceeded the redirect limit")


class WebsiteAgent:
    """
    Analyzes website security characteristics (HTTPS, TLD reputation,
    reachability, career endpoint presence).
    Gracefully degrades failures into 'unknown' rather than 'fraud'.
    """

    SUSPICIOUS_TLDS = {".xyz", ".top", ".buzz", ".click", ".link", ".rest", ".online", ".site", ".work"}
    TRUSTED_TLDS = {".edu", ".gov", ".org", ".com", ".net", ".io", ".ai", ".co"}

    def analyze(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        url = job_data.get("company_website", "").strip()

        if not url:
            return {
                "category": "website",
                "status": "unknown",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.8,
                "quality": 0.5,
                "confidence": 0.5,
                "explanation": "No company website URL provided for technical audit.",
                "signals": ["Website URL unprovided"]
            }

        domain = extract_domain(url)
        signals = []

        is_https = url.lower().startswith("https://")
        if is_https:
            signals.append("Enforces HTTPS TLS encryption")
        else:
            signals.append("Missing HTTPS protocol or uses insecure HTTP")

        is_reachable = False
        try:
            status_code = _probe_website(url)
            if status_code < 400:
                is_reachable = True
                signals.append(f"Server reachable (HTTP {status_code})")
        except WebsiteProbeError:
            is_reachable = False
            signals.append("Live web probe unreachable or timed out")

        # TLD analysis
        has_suspicious_tld = any(domain.endswith(tld) for tld in self.SUSPICIOUS_TLDS)
        if has_suspicious_tld:
            signals.append(f"Domain uses high-anomaly generic TLD: {domain}")

        # Synthesize state
        if has_suspicious_tld and not is_https:
            return {
                "category": "website",
                "status": "suspicious",
                "evidence_state": "negative",
                "score": -0.60,
                "weight": 0.9,
                "quality": 0.80,
                "confidence": 0.80,
                "explanation": f"Website domain '{domain}' uses unencrypted HTTP and a high-risk generic TLD commonly associated with disposable sites.",
                "signals": signals
            }
        elif is_https and is_reachable:
            return {
                "category": "website",
                "status": "verified",
                "evidence_state": "positive",
                "score": 0.70,
                "weight": 0.9,
                "quality": 0.85,
                "confidence": 0.85,
                "explanation": f"Domain '{domain}' verified with active HTTPS encryption and verified HTTP response.",
                "signals": signals
            }
        elif is_https:
            return {
                "category": "website",
                "status": "partially_verified",
                "evidence_state": "positive",
                "score": 0.25,
                "weight": 0.7,
                "quality": 0.65,
                "confidence": 0.65,
                "explanation": f"HTTPS configured for '{domain}'. Live web endpoint was slow to respond or firewalled.",
                "signals": signals
            }
        else:
            return {
                "category": "website",
                "status": "unknown",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.6,
                "quality": 0.50,
                "confidence": 0.50,
                "explanation": f"Unable to verify technical availability of '{domain}'. Evaluated as unknown.",
                "signals": signals
            }
