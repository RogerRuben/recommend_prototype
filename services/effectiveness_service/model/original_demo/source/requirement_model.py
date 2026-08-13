# -*- coding: utf-8 -*-
"""Score schemes relative to a new technical protocol fixed at 100 points."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from project_excel import AttributeSpec, ProjectDataset, RequirementProfile, RequirementSpec


DECISION_LABELS = {
    "direct_reuse": "达到或超过协议，具备直接复用基础",
    "local_improvement": "接近协议，小幅改进后可复用",
    "major_improvement": "与协议差距较大，需要较大改进",
    "redesign": "与协议差距很大，建议重新研制",
    "legacy_generic": "未设置新技术协议",
}
_DEFAULT_PROFILE = object()

REQUIREMENT_TYPE_LABELS = {
    "at_least": "越大越好",
    "at_most": "越小越好",
    "within_range": "区间型",
    "target": "目标值型",
    "higher_better": "越大越好",
    "lower_better": "越小越好",
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


@dataclass
class AttributeRequirementAssessment:
    attribute_key: str
    attribute_label: str
    unit: str
    value: Optional[float]
    requirement_type: str
    requirement_label: str
    requirement_text: str
    satisfaction: float
    weight: float
    weighted_score: float
    met: bool
    hard_requirement: bool
    hard_gap: bool
    gap: Optional[float]
    explanation: str
    design_stage: int
    reference_value: Optional[float] = None
    relative_score_percent: float = 0.0
    better_than_reference: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RequirementAssessment:
    profile_id: Optional[str]
    profile_name: str
    coverage: float
    coverage_percent: float
    decision: str
    decision_label: str
    hard_gap_count: int
    hard_gaps: List[str]
    attributes: List[AttributeRequirementAssessment] = field(default_factory=list)
    stage_weight_share: Dict[int, float] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=dict)
    reference_score: float = 100.0
    scoring_mode: str = "protocol_reference_100"
    weight_source: str = "design_stage_prior_50_30_20"

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["attributes"] = [item.to_dict() for item in self.attributes]
        return result


class RequirementEvaluator:
    """Use protocol values only at scoring time; never train preference models here."""

    DEFAULT_STAGE_SHARES = {1: 0.50, 2: 0.30, 3: 0.20}

    def __init__(
        self,
        project: ProjectDataset,
        profile: Any = _DEFAULT_PROFILE,
        attribute_weights: Optional[Dict[str, float]] = None,
        weight_source: Optional[str] = None,
    ) -> None:
        self.project = project
        self.profile = project.default_requirement_profile() if profile is _DEFAULT_PROFILE else profile
        self.attributes = project.attribute_by_key()
        self.attribute_weights = dict(attribute_weights or {})
        self.weight_source = weight_source or (
            "learned_generic_preference_weights"
            if self.attribute_weights
            else "design_stage_prior_50_30_20"
        )

    def evaluate(self, params: Dict[str, Any]) -> RequirementAssessment:
        if self.profile is None:
            return RequirementAssessment(
                profile_id=None,
                profile_name="未设置新技术协议",
                coverage=0.0,
                coverage_percent=0.0,
                decision="legacy_generic",
                decision_label=DECISION_LABELS["legacy_generic"],
                hard_gap_count=0,
                hard_gaps=[],
            )

        weights, stage_shares = self._attribute_weights()
        assessments: List[AttributeRequirementAssessment] = []
        for requirement in self.profile.requirements:
            spec = self.attributes[requirement.attribute_key]
            assessments.append(
                self._evaluate_attribute(
                    spec,
                    requirement,
                    self._numeric_value(params.get(requirement.attribute_key)),
                    weights[spec.key],
                )
            )

        relative_utility = clamp(sum(item.weighted_score for item in assessments), 0.0, 2.0)
        hard_gaps = [item.attribute_label for item in assessments if item.hard_gap]
        decision = self._decision(relative_utility, bool(hard_gaps))
        return RequirementAssessment(
            profile_id=self.profile.id,
            profile_name=self.profile.name,
            coverage=round(relative_utility, 6),
            coverage_percent=round(relative_utility * 100.0, 2),
            decision=decision,
            decision_label=DECISION_LABELS[decision],
            hard_gap_count=len(hard_gaps),
            hard_gaps=hard_gaps,
            attributes=assessments,
            stage_weight_share=stage_shares,
            thresholds={
                "direct_reuse": self.profile.direct_reuse_threshold,
                "improvement": self.profile.improvement_threshold,
                "redesign": self.profile.redesign_threshold,
            },
            weight_source=self.weight_source,
        )

    def _attribute_weights(self) -> Tuple[Dict[str, float], Dict[int, float]]:
        assert self.profile is not None
        requirement_keys = [item.attribute_key for item in self.profile.requirements]
        prior, stage_shares = self._stage_prior(requirement_keys)
        if not self.attribute_weights:
            return prior, stage_shares
        combined = {
            key: max(0.0, float(self.attribute_weights.get(key, prior.get(key, 0.0))))
            for key in requirement_keys
        }
        total = sum(combined.values())
        if total <= 1e-12:
            return prior, stage_shares
        return {key: value / total for key, value in combined.items()}, stage_shares

    def _stage_prior(self, keys: List[str]) -> Tuple[Dict[str, float], Dict[int, float]]:
        stage_members: Dict[int, List[str]] = {}
        for key in keys:
            stage_members.setdefault(self.attributes[key].design_stage, []).append(key)
        active_total = sum(self.DEFAULT_STAGE_SHARES.get(stage, 0.0) for stage in stage_members)
        if active_total <= 0.0:
            equal = 1.0 / max(1, len(keys))
            return {key: equal for key in keys}, {}
        stage_shares = {
            stage: self.DEFAULT_STAGE_SHARES.get(stage, 0.0) / active_total
            for stage in stage_members
        }
        weights: Dict[str, float] = {}
        for stage, members in stage_members.items():
            for key in members:
                weights[key] = stage_shares[stage] / len(members)
        return weights, stage_shares

    @staticmethod
    def _numeric_value(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _reference_value(requirement: RequirementSpec) -> Optional[float]:
        if requirement.target_value is not None:
            return float(requirement.target_value)
        if requirement.requirement_type == "at_least" and requirement.minimum is not None:
            return float(requirement.minimum)
        if requirement.requirement_type == "at_most" and requirement.maximum is not None:
            return float(requirement.maximum)
        if requirement.minimum is not None and requirement.maximum is not None:
            return 0.5 * (float(requirement.minimum) + float(requirement.maximum))
        return None

    def _evaluate_attribute(
        self,
        spec: AttributeSpec,
        requirement: RequirementSpec,
        value: Optional[float],
        weight: float,
    ) -> AttributeRequirementAssessment:
        reference = self._reference_value(requirement)
        requirement_text = (
            f"协议100分参考值 {reference:g} {spec.unit}"
            if reference is not None
            else "协议参考值缺失"
        )
        if value is None or reference is None:
            relative = 0.0
            met = False
            gap = None
            better = False
            explanation = f"{spec.label}没有可比较的数值，暂按0分处理。"
        else:
            relative, met, gap, better, explanation = self._score_value(
                spec, requirement, value, reference
            )
        hard_gap = bool(requirement.hard_requirement and not met)
        return AttributeRequirementAssessment(
            attribute_key=spec.key,
            attribute_label=spec.label,
            unit=spec.unit,
            value=value,
            requirement_type=requirement.requirement_type,
            requirement_label=REQUIREMENT_TYPE_LABELS.get(requirement.requirement_type, "协议参考"),
            requirement_text=requirement_text,
            satisfaction=round(relative, 6),
            weight=round(weight, 6),
            weighted_score=round(relative * weight, 6),
            met=met,
            hard_requirement=requirement.hard_requirement,
            hard_gap=hard_gap,
            gap=None if gap is None else round(gap, max(3, spec.precision)),
            explanation=explanation,
            design_stage=spec.design_stage,
            reference_value=reference,
            relative_score_percent=round(relative * 100.0, 2),
            better_than_reference=better,
        )

    def _score_value(
        self,
        spec: AttributeSpec,
        requirement: RequirementSpec,
        value: float,
        reference: float,
    ) -> Tuple[float, bool, float, bool, str]:
        assert spec.generation_min is not None and spec.generation_max is not None
        lo = float(spec.generation_min)
        hi = float(spec.generation_max)
        span = max(hi - lo, 1e-12)
        kind = requirement.requirement_type
        if kind in {"higher_better", "at_least"}:
            relative = clamp(1.0 + (value - reference) / span, 0.0, 2.0)
            met = value >= reference
            gap = max(0.0, reference - value)
            better = value > reference
        elif kind in {"lower_better", "at_most"}:
            relative = clamp(1.0 + (reference - value) / span, 0.0, 2.0)
            met = value <= reference
            gap = max(0.0, value - reference)
            better = value < reference
        else:
            if value <= reference:
                relative = self._linear(value, lo, reference)
            else:
                relative = self._linear(value, hi, reference)
            tolerance = max(float(requirement.tolerance), 0.5 * (10.0 ** (-spec.precision)))
            gap = max(0.0, abs(value - reference) - tolerance)
            met = gap <= 0.0
            better = False
        direction = "达到" if met else "未达到"
        comparison = "，优于协议参考" if better else ""
        explanation = (
            f"{spec.label}{direction}100分参考值{comparison}；"
            f"该属性相对得分 {relative * 100.0:.1f} 分。"
        )
        return relative, met, gap, better, explanation

    @staticmethod
    def _linear(value: float, zero: float, one: float) -> float:
        width = one - zero
        if abs(width) <= 1e-12:
            return 1.0 if value == one else 0.0
        return clamp((value - zero) / width, 0.0, 1.0)

    def _decision(self, score_ratio: float, has_hard_gap: bool) -> str:
        assert self.profile is not None
        if score_ratio >= self.profile.direct_reuse_threshold and not has_hard_gap:
            return "direct_reuse"
        if score_ratio >= self.profile.improvement_threshold:
            return "local_improvement"
        if score_ratio >= self.profile.redesign_threshold:
            return "major_improvement"
        return "redesign"
