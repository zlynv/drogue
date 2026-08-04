"""Protection layer — DDoS detection, auto-ban, circuit breaker."""

from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.circuit import CircuitBreaker, CircuitState
from drogue.protection.ddos import DDoSDetector
from drogue.protection.pipeline import PipelineResult, ProtectionPipeline

__all__ = [
    "DDoSDetector",
    "ProgressiveBanManager",
    "CircuitBreaker",
    "CircuitState",
    "ProtectionPipeline",
    "PipelineResult",
]
