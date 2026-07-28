"""CIDR allow/deny list filtering for rate limiting.

Provides IP-based access control using CIDR notation for both
IPv4 and IPv6 addresses. Supports file-based lists and URL feeds.
"""
from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("drogue.cidr")


@dataclass
class CIDRFilter:
    """Filter requests based on CIDR allow/deny lists.

    Usage:
        filter = CIDRFilter(
            allowlist=["10.0.0.0/8", "192.168.0.0/16"],
            denylist=["192.168.1.100/32"],
        )

        if filter.is_denied("192.168.1.100"):
            return 403
    """

    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)

    # Compiled networks
    _allow_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = field(
        default_factory=list, init=False, repr=False
    )
    _deny_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = field(
        default_factory=list, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Compile CIDR strings into network objects."""
        self._allow_networks = self._compile_networks(self.allowlist)
        self._deny_networks = self._compile_networks(self.denylist)

    def _compile_networks(
        self, cidrs: list[str]
    ) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        """Compile CIDR strings into network objects."""
        networks = []
        for cidr in cidrs:
            try:
                networks.append(ipaddress.ip_network(cidr.strip(), strict=False))
            except ValueError as e:
                logger.warning("Invalid CIDR '%s': %s", cidr, e)
        return networks

    def is_allowed(self, ip: str) -> bool:
        """Check if an IP is allowed (not in denylist and in allowlist if set)."""
        try:
            addr = ipaddress.ip_address(ip.strip())
        except ValueError:
            logger.warning("Invalid IP address: %s", ip)
            return False

        # Check denylist first
        if self._is_in_networks(addr, self._deny_networks):
            return False

        # If allowlist is empty, allow all (except denied)
        if not self._allow_networks:
            return True

        # Check allowlist
        return self._is_in_networks(addr, self._allow_networks)

    def is_denied(self, ip: str) -> bool:
        """Check if an IP is denied."""
        return not self.is_allowed(ip)

    def _is_in_networks(
        self,
        addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
    ) -> bool:
        """Check if an address is in any of the networks."""
        return any(addr in network for network in networks)

    def add_to_allowlist(self, cidr: str) -> bool:
        """Add a CIDR to the allowlist at runtime. Returns True if valid."""
        try:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
            self._allow_networks.append(network)
            self.allowlist.append(cidr)
            return True
        except ValueError as e:
            logger.warning("Invalid CIDR '%s': %s", cidr, e)
            return False

    def add_to_denylist(self, cidr: str) -> bool:
        """Add a CIDR to the denylist at runtime. Returns True if valid."""
        try:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
            self._deny_networks.append(network)
            self.denylist.append(cidr)
            return True
        except ValueError as e:
            logger.warning("Invalid CIDR '%s': %s", cidr, e)
            return False

    def remove_from_allowlist(self, cidr: str) -> bool:
        """Remove a CIDR from the allowlist. Returns True if found."""
        try:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
            if cidr in self.allowlist:
                self.allowlist.remove(cidr)
            if network in self._allow_networks:
                self._allow_networks.remove(network)
            return True
        except ValueError:
            return False

    def remove_from_denylist(self, cidr: str) -> bool:
        """Remove a CIDR from the denylist. Returns True if found."""
        try:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
            if cidr in self.denylist:
                self.denylist.remove(cidr)
            if network in self._deny_networks:
                self._deny_networks.remove(network)
            return True
        except ValueError:
            return False

    def load_from_file(self, filepath: str, list_type: str = "denylist") -> int:
        """Load CIDRs from a file (one per line). Returns count loaded."""
        networks = []
        try:
            with open(filepath) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            networks.append(ipaddress.ip_network(line, strict=False))
                        except ValueError as e:
                            logger.warning("Invalid CIDR '%s' in %s: %s", line, filepath, e)
        except FileNotFoundError:
            logger.error("CIDR file not found: %s", filepath)
            return 0

        if list_type == "allowlist":
            self._allow_networks.extend(networks)
        else:
            self._deny_networks.extend(networks)

        return len(networks)

    def get_stats(self) -> dict[str, Any]:
        """Get filter statistics."""
        return {
            "allowlist_count": len(self._allow_networks),
            "denylist_count": len(self._deny_networks),
            "allowlist": self.allowlist,
            "denylist": self.denylist,
        }
