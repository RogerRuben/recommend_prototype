# -*- coding: utf-8 -*-
"""Shared model/business field-type compatibility rules."""
from __future__ import print_function


def _clean(value):
    return str(value or "").strip().lower()


def canonical_model_type(value):
    aliases = {
        "numeric": "number",
        "float": "number",
        "continuous": "number",
        "int": "integer",
        "bool": "boolean",
        "categorical": "enum",
        "category": "enum",
        "text": "enum",
    }
    cleaned = _clean(value)
    return aliases.get(cleaned, cleaned)


def model_types_compatible(actual, expected):
    """Return True when two declarations share the same wire representation.

    Business metadata may preserve a more useful editor type (IP grade,
    boolean, or integer) while an effectiveness runtime exposes the value as a
    numeric feature.  Those pairs are compatible; enum and free numeric fields
    remain deliberately distinct.
    """
    actual = canonical_model_type(actual)
    expected = canonical_model_type(expected)
    if actual == expected:
        return True
    compatible_groups = (
        {"number", "integer"},
        {"integer", "ip_grade"},
        {"integer", "boolean"},
        {"number", "boolean"},
        {"number", "ip_grade"},
    )
    return any(set((actual, expected)).issubset(group) for group in compatible_groups)
