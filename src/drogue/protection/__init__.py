"""Protection layer - DDoS detection, auto-ban, circuit breaker."""

from drogue.protection.adaptive import AdaptiveRateLimiter
from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.cidr import CIDRFilter
from drogue.protection.circuit import CircuitBreaker, CircuitState
from drogue.protection.ddos import DDoSDetector
from drogue.protection.pipeline import PipelineResult, ProtectionPipeline
from drogue.protection.probes import ProbeDetector
from drogue.protection.sentinel import SentinelDetector, extract_features
from drogue.protection.trust import TrustLevel, TrustManager

__all__ = [
    "DDoSDetector",
    "ProgressiveBanManager",
    "CircuitBreaker",
    "CircuitState",
    "ProtectionPipeline",
    "PipelineResult",
    "ProbeDetector",
    "TrustManager",
    "TrustLevel",
    "SentinelDetector",
    "extract_features",
    "CIDRFilter",
    "AdaptiveRateLimiter",
]
