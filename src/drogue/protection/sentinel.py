"""Sentinel Model for streaming anomaly detection.

Implements Half-Space Trees for online anomaly detection that
adapts to concept drift and catches zero-day attack patterns.

Properties:
- Single-pass: O(1) per data point
- Bounded memory: fixed-size sketch (~5MB)
- No labels needed: learns "normal" from recent traffic
- Concept drift aware: automatically adapts to pattern changes
- Self-calibrating: maintains target false positive rate

Based on: Tan, S.C., et al. "Fast Anomaly Detection for
Streaming Data" (IJCAI 2011)
"""
from __future__ import annotations

import logging
import math
import random
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("drogue.sentinel")


@dataclass
class _TreeNode:
    """Node in a Half-Space Tree."""

    split_feature: int = 0
    split_value: float = 0.0
    left: _TreeNode | None = None
    right: _TreeNode | None = None
    is_leaf: bool = False
    depth: int = 0


class HalfSpaceTree:
    """Online anomaly detection via isolation trees.

    Properties:
    - Single-pass: O(1) per data point
    - Bounded memory: fixed-size forest
    - Concept drift aware: sliding window of reference points
    - No labels needed: purely unsupervised
    - Self-calibrating: maintains target false positive rate

    Usage:
        tree = HalfSpaceTree(n_features=5, n_trees=25)

        # Score a data point (higher = more anomalous)
        score = tree.score([0.5, 0.3, 0.8, 0.1, 0.9])

        # Update reference window
        tree.update([0.5, 0.3, 0.8, 0.1, 0.9])
    """

    def __init__(
        self,
        n_features: int = 5,
        n_trees: int = 25,
        window_size: int = 256,
        max_depth: int = 15,
        random_state: int | None = None,
    ):
        """Initialize the Half-Space Tree.

        Args:
            n_features: Number of input features.
            n_trees: Number of trees in the forest.
            window_size: Size of the reference window.
            max_depth: Maximum depth of each tree.
            random_state: Random seed for reproducibility.
        """
        self.n_features = n_features
        self.n_trees = n_trees
        self.window_size = window_size
        self.max_depth = max_depth

        self._rng = random.Random(random_state)
        self._trees: list[_TreeNode] = []
        self._reference_window: deque[list[float]] = deque(maxlen=window_size)
        self._sample_count = 0

        # Build initial trees
        self._rebuild()

    def score(self, point: list[float]) -> float:
        """Return anomaly score (higher = more anomalous).

        The score is based on the average path length in the forest.
        Anomalous points are isolated quickly (short path = high score).

        Args:
            point: Input feature vector.

        Returns:
            Anomaly score (negative average depth, higher = more anomalous).
        """
        if len(point) != self.n_features:
            raise ValueError(
                f"Expected {self.n_features} features, got {len(point)}"
            )

        if not self._trees:
            # No reference data yet (need >= 2 samples to build trees).
            # Neutral score: neither normal nor anomalous.
            return 0.0

        scores = []
        for tree in self._trees:
            depth = self._traverse(tree, point, 0)
            scores.append(depth)

        # Negative average depth: shallow path = high score
        avg_depth = sum(scores) / len(scores)
        return -avg_depth

    def update(self, point: list[float]) -> None:
        """Update reference window with new data point.

        Args:
            point: Input feature vector.
        """
        self._reference_window.append(point)
        self._sample_count += 1

        # Periodically rebuild trees with new reference data
        if self._sample_count % self.window_size == 0:
            self._rebuild()

    def get_feature_importance(self) -> list[float]:
        """Get feature importance based on split frequency.

        Returns:
            List of importance scores (higher = more important).
        """
        importance = [0.0] * self.n_features
        for tree in self._trees:
            self._count_splits(tree, importance)

        # Normalize
        total = sum(importance)
        if total > 0:
            importance = [x / total for x in importance]

        return importance

    def _traverse(self, node: _TreeNode | None, point: list[float], depth: int) -> int:
        """Traverse tree and return depth reached."""
        if node is None or node.is_leaf or depth >= self.max_depth:
            return depth

        if point[node.split_feature] < node.split_value:
            return self._traverse(node.left, point, depth + 1)
        else:
            return self._traverse(node.right, point, depth + 1)

    def _count_splits(self, node: _TreeNode | None, importance: list[float]) -> None:
        """Count feature splits for importance calculation."""
        if node is None or node.is_leaf:
            return

        importance[node.split_feature] += 1
        self._count_splits(node.left, importance)
        self._count_splits(node.right, importance)

    def _rebuild(self) -> None:
        """Rebuild trees with current reference window."""
        if len(self._reference_window) < 2:
            return

        self._trees = []
        for _ in range(self.n_trees):
            tree = self._build_tree(list(self._reference_window), depth=0)
            self._trees.append(tree)

    def _build_tree(self, data: list[list[float]], depth: int) -> _TreeNode:
        """Build a single isolation tree."""
        if depth >= self.max_depth or len(data) <= 1:
            return _TreeNode(is_leaf=True, depth=depth)

        # Random feature and split value
        feature = self._rng.randint(0, self.n_features - 1)

        # Get min/max for this feature
        values = [row[feature] for row in data]
        min_val, max_val = min(values), max(values)

        if min_val == max_val:
            return _TreeNode(is_leaf=True, depth=depth)

        split_value = self._rng.uniform(min_val, max_val)

        # Split data
        left_data = [row for row in data if row[feature] < split_value]
        right_data = [row for row in data if row[feature] >= split_value]

        # Recurse
        left = self._build_tree(left_data, depth + 1) if left_data else None
        right = self._build_tree(right_data, depth + 1) if right_data else None

        return _TreeNode(
            split_feature=feature,
            split_value=split_value,
            left=left,
            right=right,
            is_leaf=False,
            depth=depth,
        )


class SentinelDetector:
    """Streaming anomaly detector for DDoS detection.

    Combines Half-Space Trees with adaptive thresholding for
    online anomaly detection that catches zero-day attacks.

    Usage:
        detector = SentinelDetector(n_features=5)

        # Extract features from request context
        features = extract_features(request_context)

        # Score and update
        is_anomaly = detector.analyze(features)

        # Get current threshold
        threshold = detector.get_threshold()
    """

    def __init__(
        self,
        n_features: int = 5,
        n_trees: int = 25,
        window_size: int = 256,
        max_depth: int = 15,
        target_fpr: float = 0.001,
        score_window: int = 1000,
        random_state: int | None = None,
    ):
        """Initialize the Sentinel detector.

        Args:
            n_features: Number of input features.
            n_trees: Number of trees in the forest.
            window_size: Size of the reference window.
            max_depth: Maximum depth of each tree.
            target_fpr: Target false positive rate (0.001 = 0.1%).
            score_window: Window size for adaptive threshold calculation.
            random_state: Random seed for reproducibility.
        """
        self.target_fpr = target_fpr
        self.score_window = score_window

        self._tree = HalfSpaceTree(
            n_features=n_features,
            n_trees=n_trees,
            window_size=window_size,
            max_depth=max_depth,
            random_state=random_state,
        )

        self._lock = threading.RLock()
        self._scores: deque[float] = deque(maxlen=score_window)
        self._anomaly_count = 0
        self._total_count = 0

    def analyze(self, features: list[float]) -> bool:
        """Analyze features and return True if anomalous.

        The adaptive threshold is computed over the PREVIOUS score window
        (excluding the current score), so a new maximum can never blind
        the detector: comparing a score against a percentile that includes
        itself would make `score > max(window ∪ {score})` always False.

        Args:
            features: Input feature vector.

        Returns:
            True if the features are anomalous.
        """
        with self._lock:
            score = self._tree.score(features)
            self._tree.update(features)

            # Threshold from history BEFORE appending the current score
            threshold = self._compute_threshold()

            self._scores.append(score)
            self._total_count += 1

            is_anomaly = score > threshold

            if is_anomaly:
                self._anomaly_count += 1
                logger.info(
                    "sentinel_anomaly score=%.3f threshold=%.3f",
                    score,
                    threshold,
                )

            return is_anomaly

    def get_threshold(self) -> float:
        """Get the current anomaly threshold."""
        with self._lock:
            return self._compute_threshold()

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        with self._lock:
            threshold = self._compute_threshold()
            return {
                "total_count": self._total_count,
                "anomaly_count": self._anomaly_count,
                "anomaly_rate": (
                    self._anomaly_count / self._total_count
                    if self._total_count > 0
                    else 0.0
                ),
                "current_threshold": threshold,
                "score_window_size": len(self._scores),
                "feature_importance": self._tree.get_feature_importance(),
            }

    def _compute_threshold(self) -> float:
        """Compute adaptive threshold from recent scores."""
        if len(self._scores) < 10:
            return 0.0

        # Sort scores and take the (1 - target_fpr) percentile.
        # Use ceiling so the index lands strictly inside the tail instead
        # of on the window maximum (which would make anomalies impossible).
        sorted_scores = sorted(self._scores)
        idx = math.ceil(len(sorted_scores) * (1.0 - self.target_fpr)) - 1
        idx = min(max(idx, 0), len(sorted_scores) - 1)
        return sorted_scores[idx]


def extract_features(context: dict[str, Any]) -> list[float]:
    """Extract features from request context for anomaly detection.

    Args:
        context: Request context dictionary with metrics.

    Returns:
        List of normalized features.
    """
    return [
        context.get("requests_per_minute", 0.0),
        context.get("unique_endpoints", 0.0),
        context.get("avg_inter_arrival_ms", 0.0),
        context.get("error_rate", 0.0),
        context.get("bytes_per_request", 0.0),
    ]
