# -*- coding: utf-8 -*-
"""Importable expert-weighted decision tree for the price service.

The training notebook originally defined :class:`TreeNode` and
:class:`ExpertWeightedTreeRegressor` inline in ``__main__``.  A pickle written
from ``__main__`` records ``__main__.ExpertWeightedTreeRegressor`` as the class
path, which the independent price service cannot import, so the exported
bundle failed to load.  Moving both classes into this stable module keeps the
pickle portable while preserving the exact training behaviour.
"""
from __future__ import print_function

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin


@dataclass
class TreeNode:
    feature: str = None
    threshold: float = None
    left: object = None
    right: object = None
    value: float = None
    min_price: float = None
    max_price: float = None
    sample_num: int = 0
    is_leaf: bool = False


class ExpertWeightedTreeRegressor(BaseEstimator, RegressorMixin):
    def __init__(self, max_depth=10, min_samples_leaf=1, lambda_expert=0.5, min_gain_split=0.0, expert_map=None):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.lambda_expert = lambda_expert
        self.min_gain_split = min_gain_split
        self.expert_map = expert_map or {}

    def fit(self, X, y):
        self.X_ = pd.DataFrame(X).copy()
        self.y_ = np.array(y).copy()
        self.columns_ = self.X_.columns.tolist()
        self.root_ = self._build_tree(self.X_, self.y_, depth=0, used_features=set())
        return self

    def _sse(self, y):
        if len(y) == 0:
            return 0.0
        return np.sum((y - np.mean(y)) ** 2)

    def _expert_norm(self, feature):
        s = self.expert_map.get(feature, 1.0)
        if s is None or pd.isna(s) or not np.isfinite(s):
            s = 1.0
        s = float(s)
        s = max(1.0, min(5.0, s))
        return (s - 1.0) / 4.0  # 映射到 0~1

    def _best_split(self, X, y, used_features):
        parent_sse = self._sse(y)
        best_score = -np.inf
        best_feature = None
        best_threshold = None
        best_left_idx = None
        best_right_idx = None

        for feature in X.columns:
            # 如果你不想重复用同一个特征，取消下一行注释
            if feature in used_features:
                continue

            values = np.unique(X[feature].values)
            if len(values) <= 1:
                continue

            thresholds = (values[:-1] + values[1:]) / 2.0

            for thr in thresholds:
                left_idx = X[feature].values <= thr
                right_idx = ~left_idx

                if left_idx.sum() < self.min_samples_leaf or right_idx.sum() < self.min_samples_leaf:
                    continue

                y_left = y[left_idx]
                y_right = y[right_idx]

                data_gain = parent_sse - (self._sse(y_left) + self._sse(y_right))
                if data_gain < self.min_gain_split:
                    continue

                expert_norm = self._expert_norm(feature)
                score = data_gain * (1.0 + self.lambda_expert * expert_norm)

                if score > best_score:
                    best_score = score
                    best_feature = feature
                    best_threshold = thr
                    best_left_idx = left_idx
                    best_right_idx = right_idx

        return best_feature, best_threshold, best_left_idx, best_right_idx

    def _build_tree(self, X, y, depth, used_features):
        price = np.exp(y)      # 如果y已经是价格，就改成 price = y

        node = TreeNode(
            value=float(np.mean(y)),
            min_price=float(np.min(price)),
            max_price=float(np.max(price)),
            sample_num=len(price)
        )

        if depth >= self.max_depth or len(y) <= 1 * self.min_samples_leaf:
            node.is_leaf = True
            return node

        feature, threshold, left_idx, right_idx = self._best_split(X, y, used_features)

        if feature is None:
            node.is_leaf = True
            return node

        node.feature = feature
        node.threshold = threshold

        new_used_features = set(used_features)
        new_used_features.add(feature)

        node.left = self._build_tree(
            X[left_idx].reset_index(drop=True),
            y[left_idx],
            depth + 1,
            new_used_features
        )
        node.right = self._build_tree(
            X[right_idx].reset_index(drop=True),
            y[right_idx],
            depth + 1,
            new_used_features
        )
        return node

    def _predict_one(self, x, node):
        if node.is_leaf or node.feature is None:
            return node.value
        if x[node.feature] <= node.threshold:
            return self._predict_one(x, node.left)
        else:
            return self._predict_one(x, node.right)

    def predict(self, X):
        X = pd.DataFrame(X).copy()
        return np.array([self._predict_one(X.iloc[i], self.root_) for i in range(len(X))])

    @property
    def feature_importances_(self):
        """Split-count importance so the notebook's diagnostics keep working.

        Not used by the service prediction path; it only avoids an
        ``AttributeError`` in the training notebook.
        """
        columns = getattr(self, "columns_", [])
        counts = dict((c, 0) for c in columns)

        def walk(node):
            if node is None or node.is_leaf or node.feature is None:
                return
            if node.feature in counts:
                counts[node.feature] += 1
            walk(node.left)
            walk(node.right)

        walk(getattr(self, "root_", None))
        total = sum(counts.values()) or 1
        return np.array([counts.get(c, 0) / total for c in columns], dtype=float)
