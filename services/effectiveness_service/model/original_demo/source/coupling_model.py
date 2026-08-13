# -*- coding: utf-8 -*-
"""Monotonic directed-coupling surrogates learned from existing schemes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.optimize import lsq_linear

from project_excel import AttributeSpec, ProjectDataError, ProjectDataset


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class SourceEffect:
    key: str
    label: str
    direction: str
    normalized_coefficient: float
    physical_coefficient: float
    source_unit: str


@dataclass
class TargetAssessment:
    target_key: str
    target_label: str
    target_unit: str
    actual: float
    predicted: float
    lower: float
    upper: float
    residual: float
    status: str
    boundary_distance: float
    severity: float
    message: str
    source_contributions: List[Dict[str, Any]]


@dataclass
class MonotonicTargetModel:
    target_key: str
    target_label: str
    target_unit: str
    source_effects: List[SourceEffect]
    intercept: float
    lower_offset: float
    upper_offset: float
    rmse: float
    r2: float
    sample_count: int
    training_coverage: float
    confidence: str
    target_min: float
    target_max: float
    source_ranges: Dict[str, List[float]]

    def normalized_sources(self, params: Dict[str, Any]) -> List[float]:
        values = []
        for effect in self.source_effects:
            lo, hi = self.source_ranges[effect.key]
            values.append(clamp((float(params[effect.key]) - lo) / max(hi - lo, 1e-9), 0.0, 1.0))
        return values

    def predict_normalized(self, params: Dict[str, Any]) -> float:
        value = self.intercept
        for effect, source_value in zip(self.source_effects, self.normalized_sources(params)):
            value += effect.normalized_coefficient * source_value
        return value

    def denormalize_target(self, normalized: float) -> float:
        return self.target_min + normalized * (self.target_max - self.target_min)

    def predict(self, params: Dict[str, Any]) -> float:
        return self.denormalize_target(self.predict_normalized(params))

    def band(self, params: Dict[str, Any]) -> Dict[str, float]:
        predicted_normalized = self.predict_normalized(params)
        lower = self.denormalize_target(predicted_normalized + self.lower_offset)
        upper = self.denormalize_target(predicted_normalized + self.upper_offset)
        lo = clamp(min(lower, upper), self.target_min, self.target_max)
        hi = clamp(max(lower, upper), self.target_min, self.target_max)
        if hi - lo < 1e-9:
            pad = 0.02 * (self.target_max - self.target_min)
            lo = clamp(lo - pad, self.target_min, self.target_max)
            hi = clamp(hi + pad, self.target_min, self.target_max)
        return {"predicted": self.predict(params), "lower": lo, "upper": hi}

    def assess(self, params: Dict[str, Any]) -> TargetAssessment:
        band = self.band(params)
        actual = float(params[self.target_key])
        width = max(band["upper"] - band["lower"], 0.04 * (self.target_max - self.target_min), 1e-9)
        residual = actual - band["predicted"]
        if actual < band["lower"]:
            status = "below_band"
            distance = band["lower"] - actual
            severity = clamp(distance / width, 0.05, 1.0)
            message = (
                f"当前 {self.target_label} 为 {actual:.3g} {self.target_unit}，低于已有样本条件经验带 "
                f"[{band['lower']:.3g}, {band['upper']:.3g}]。可能是新结构带来的改进，也可能不满足物理支撑，需要专家确认。"
            )
        elif actual > band["upper"]:
            status = "above_band"
            distance = actual - band["upper"]
            severity = clamp(distance / width, 0.05, 1.0)
            message = (
                f"当前 {self.target_label} 为 {actual:.3g} {self.target_unit}，高于已有样本条件经验带 "
                f"[{band['lower']:.3g}, {band['upper']:.3g}]。物理上未必不可行，但组合偏离已有工程样本。"
            )
        else:
            relative = min(actual - band["lower"], band["upper"] - actual) / width
            if relative < 0.12:
                status = "near_boundary"
                severity = 0.30
                message = (
                    f"{self.target_label} 位于条件经验带 [{band['lower']:.3g}, {band['upper']:.3g}] 的边缘，"
                    "适合用于确认耦合边界。"
                )
            else:
                status = "within_band"
                severity = 0.05
                message = (
                    f"{self.target_label} 位于已有样本学习到的条件经验带 "
                    f"[{band['lower']:.3g}, {band['upper']:.3g}] 内。"
                )
            distance = min(actual - band["lower"], band["upper"] - actual)
        return TargetAssessment(
            target_key=self.target_key,
            target_label=self.target_label,
            target_unit=self.target_unit,
            actual=round(actual, 6),
            predicted=round(band["predicted"], 6),
            lower=round(band["lower"], 6),
            upper=round(band["upper"], 6),
            residual=round(residual, 6),
            status=status,
            boundary_distance=round(distance, 6),
            severity=round(severity, 3),
            message=message,
            source_contributions=self.source_contributions(params),
        )

    def source_contributions(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for effect in self.source_effects:
            lo, _ = self.source_ranges[effect.key]
            value = float(params[effect.key])
            contribution = effect.physical_coefficient * (value - lo)
            output.append(
                {
                    "source_key": effect.key,
                    "source_label": effect.label,
                    "source_value": round(value, 6),
                    "source_unit": effect.source_unit,
                    "direction": effect.direction,
                    "physical_coefficient": effect.physical_coefficient,
                    "target_contribution_from_generation_min": round(contribution, 6),
                    "target_unit": self.target_unit,
                }
            )
        return sorted(
            output,
            key=lambda item: abs(float(item["target_contribution_from_generation_min"])),
            reverse=True,
        )

    def summary(self) -> Dict[str, Any]:
        data = asdict(self)
        data["source_effects"] = [asdict(item) for item in self.source_effects]
        return data


class CouplingSystem:
    def __init__(
        self,
        project: ProjectDataset,
        models: Dict[str, MonotonicTargetModel],
        direction_only: Optional[Dict[str, List[Any]]] = None,
    ):
        self.project = project
        self.models = models
        self.direction_only = direction_only or {}
        self.edges_by_target: Dict[str, List[Any]] = {}
        for edge in project.couplings:
            self.edges_by_target.setdefault(edge.target_key, []).append(edge)

    @classmethod
    def fit(cls, project: ProjectDataset, ridge: float = 0.025) -> "CouplingSystem":
        by_key = project.attribute_by_key()
        grouped: Dict[str, List[Any]] = {}
        for edge in project.couplings:
            grouped.setdefault(edge.target_key, []).append(edge)
        models: Dict[str, MonotonicTargetModel] = {}
        direction_only: Dict[str, List[Any]] = {}
        for target_key, edges in grouped.items():
            target_spec = by_key[target_key]
            if not target_spec.is_numeric:
                continue
            source_specs = [by_key[edge.source_key] for edge in edges]
            if any(not item.is_numeric for item in source_specs):
                raise ProjectDataError(f"目标“{target_spec.label}”的耦合源必须都是数值属性。")
            if len(project.schemes) < len(source_specs) + 2:
                direction_only[target_key] = edges
                continue
            models[target_key] = cls._fit_target(project, target_spec, source_specs, edges, ridge)
        return cls(project, models, direction_only=direction_only)

    @staticmethod
    def _fit_target(
        project: ProjectDataset,
        target: AttributeSpec,
        sources: List[AttributeSpec],
        edges: List[Any],
        ridge: float,
    ) -> MonotonicTargetModel:
        assert target.generation_min is not None and target.generation_max is not None
        source_ranges: Dict[str, List[float]] = {}
        rows: List[List[float]] = []
        y_values: List[float] = []
        for scheme in project.schemes:
            row = [1.0]
            for source in sources:
                assert source.generation_min is not None and source.generation_max is not None
                source_ranges[source.key] = [source.generation_min, source.generation_max]
                row.append(
                    clamp(
                        (float(scheme.params[source.key]) - source.generation_min)
                        / max(source.generation_max - source.generation_min, 1e-9),
                        0.0,
                        1.0,
                    )
                )
            rows.append(row)
            y_values.append(
                (float(scheme.params[target.key]) - target.generation_min)
                / max(target.generation_max - target.generation_min, 1e-9)
            )
        if len(rows) < len(sources) + 2:
            raise ProjectDataError(
                f"目标“{target.label}”只有 {len(rows)} 个样本，不足以拟合 {len(sources)} 个耦合源。"
            )
        x = np.asarray(rows, dtype=float)
        y = np.asarray(y_values, dtype=float)
        regularizer = np.zeros((len(sources), len(sources) + 1), dtype=float)
        for index in range(len(sources)):
            regularizer[index, index + 1] = ridge**0.5
        x_aug = np.vstack([x, regularizer])
        y_aug = np.concatenate([y, np.zeros(len(sources), dtype=float)])
        lower = [-np.inf]
        upper = [np.inf]
        for edge in edges:
            if edge.direction == "positive":
                lower.append(0.0)
                upper.append(np.inf)
            else:
                lower.append(-np.inf)
                upper.append(0.0)
        result = lsq_linear(x_aug, y_aug, bounds=(np.asarray(lower), np.asarray(upper)), method="trf")
        if not result.success:
            raise ProjectDataError(f"目标“{target.label}”的单调耦合代理拟合失败：{result.message}")
        coefficients = result.x
        predicted = x @ coefficients
        residuals = y - predicted
        rmse_normalized = float(np.sqrt(np.mean(residuals**2)))
        y_mean = float(np.mean(y))
        total = float(np.sum((y - y_mean) ** 2))
        r2 = 1.0 - float(np.sum(residuals**2)) / max(total, 1e-12)
        center = float(np.median(residuals))
        robust_sigma = 1.4826 * float(np.median(np.abs(residuals - center)))
        half_width = max(1.65 * max(robust_sigma, rmse_normalized), 0.035)
        lower_offset = center - half_width
        upper_offset = center + half_width
        coverage = float(np.mean((residuals >= lower_offset) & (residuals <= upper_offset)))
        target_span = target.generation_max - target.generation_min
        effects: List[SourceEffect] = []
        for source, edge, coefficient in zip(sources, edges, coefficients[1:]):
            assert source.generation_min is not None and source.generation_max is not None
            source_span = source.generation_max - source.generation_min
            physical = float(coefficient) * target_span / max(source_span, 1e-9)
            effects.append(
                SourceEffect(
                    key=source.key,
                    label=source.label,
                    direction=edge.direction,
                    normalized_coefficient=round(float(coefficient), 8),
                    physical_coefficient=round(physical, 8),
                    source_unit=source.unit,
                )
            )
        confidence = "高" if r2 >= 0.70 and len(rows) >= 25 else "中" if r2 >= 0.35 else "低"
        return MonotonicTargetModel(
            target_key=target.key,
            target_label=target.label,
            target_unit=target.unit,
            source_effects=effects,
            intercept=round(float(coefficients[0]), 10),
            lower_offset=round(lower_offset, 10),
            upper_offset=round(upper_offset, 10),
            rmse=round(rmse_normalized * target_span, 6),
            r2=round(r2, 6),
            sample_count=len(rows),
            training_coverage=round(coverage, 6),
            confidence=confidence,
            target_min=target.generation_min,
            target_max=target.generation_max,
            source_ranges=source_ranges,
        )

    def assess(self, params: Dict[str, Any]) -> List[TargetAssessment]:
        return [model.assess(params) for model in self.models.values()]

    def summaries(self) -> List[Dict[str, Any]]:
        output = [model.summary() for model in self.models.values()]
        by_key = self.project.attribute_by_key()
        for target_key, edges in self.direction_only.items():
            target = by_key[target_key]
            output.append(
                {
                    "target_key": target_key,
                    "target_label": target.label,
                    "target_unit": target.unit,
                    "source_effects": [
                        {
                            "key": edge.source_key,
                            "label": edge.source_label,
                            "direction": edge.direction,
                            "normalized_coefficient": None,
                            "physical_coefficient": None,
                            "source_unit": by_key[edge.source_key].unit,
                        }
                        for edge in edges
                    ],
                    "intercept": None,
                    "lower_offset": None,
                    "upper_offset": None,
                    "rmse": None,
                    "r2": None,
                    "sample_count": len(self.project.schemes),
                    "training_coverage": None,
                    "confidence": "方向已知、强度待学习",
                    "model_status": "direction_only",
                    "required_samples_for_point_fit": len(edges) + 2,
                    "target_min": target.generation_min,
                    "target_max": target.generation_max,
                }
            )
        return output

    def target_keys(self) -> set[str]:
        return set(self.edges_by_target)

    def probe_definition(self, target_key: str) -> Dict[str, Any]:
        """Return declared directions for a low-burden controlled coupling probe."""
        by_key = self.project.attribute_by_key()
        edges = self.edges_by_target.get(target_key, [])
        target = by_key[target_key]
        return {
            "target_key": target_key,
            "target_label": target.label,
            "target_unit": target.unit,
            "model_status": "fitted" if target_key in self.models else "direction_only",
            "sources": [
                {
                    "key": edge.source_key,
                    "label": edge.source_label,
                    "unit": by_key[edge.source_key].unit,
                    "direction": edge.direction,
                }
                for edge in edges
            ],
        }
