# -*- coding: utf-8 -*-
"""Small dependency-free estimators for the deterministic virtual fixture.

These classes are intentionally importable from a stable module path so a
protocol-4 pickle can be loaded by the price service on Python 3.8.  They are
test fixtures, not substitutes for production estimators.
"""
from __future__ import print_function

import math


class SyntheticStandardScaler(object):
    def __init__(self, mean, scale):
        self.mean = [float(value) for value in mean]
        self.scale = [max(abs(float(value)), 1e-12) for value in scale]

    def transform(self, values):
        result = []
        for row in values:
            result.append([
                (float(value) - self.mean[index]) / self.scale[index]
                for index, value in enumerate(row)
            ])
        return result


class SyntheticLinearRegressor(object):
    def __init__(self, intercept, coefficients, name="synthetic_linear"):
        self.intercept = float(intercept)
        self.coefficients = [float(value) for value in coefficients]
        self.name = str(name)

    def predict(self, values):
        result = []
        for row in values:
            value = self.intercept + sum(
                coefficient * float(item)
                for coefficient, item in zip(self.coefficients, row)
            )
            if not math.isfinite(value):
                raise ValueError("虚拟价格模型产生非有限预测")
            result.append(value)
        return result
