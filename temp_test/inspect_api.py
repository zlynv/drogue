import inspect
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm
from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm
from drogue.core.rules.rule import RateLimitRule, AlgorithmType, parse_rule_string
from drogue.core.config import DrogueConfig
from drogue.core.identity import RemoteAddressExtractor, UserExtractor, HeaderExtractor, StaticKeyExtractor
from drogue.protection.trust import TrustManager
from drogue.protection.circuit import CircuitBreaker
from drogue.protection.ddos import DDoSDetector
from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.probes import ProbeDetector
from drogue.protection.cidr import CIDRFilter
from drogue.protection.adaptive import AdaptiveRateLimiter
from drogue.defense.randomizer import DefenseRandomizer, HoneypotManager
from drogue.storage.probabilistic import CountMinSketch, BloomFilter, CuckooFilter, HyperLogLog
from drogue.observability.metrics import DrogueMetrics

classes = [
    TokenBucketAlgorithm, SlidingWindowAlgorithm, FixedWindowAlgorithm,
    RateLimitRule, DrogueConfig,
    RemoteAddressExtractor, UserExtractor, HeaderExtractor, StaticKeyExtractor,
    TrustManager, CircuitBreaker, DDoSDetector, ProgressiveBanManager,
    ProbeDetector, CIDRFilter, AdaptiveRateLimiter,
    DefenseRandomizer, HoneypotManager,
    CountMinSketch, BloomFilter, CuckooFilter, HyperLogLog,
    DrogueMetrics,
]

for cls in classes:
    name = cls.__name__
    print(f"=== {name} ===")
    try:
        print(f"  init: {inspect.signature(cls.__init__)}")
    except Exception:
        print(f"  init: (?)")
    for method_name in dir(cls):
        if method_name.startswith('_'):
            continue
        method = getattr(cls, method_name)
        if not callable(method):
            continue
        try:
            sig = inspect.signature(method)
            print(f"  {method_name}{sig}")
        except Exception:
            print(f"  {method_name} (?)")
    print()
