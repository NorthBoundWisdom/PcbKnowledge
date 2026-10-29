#!/usr/bin/env python3
"""Replay one fixed synthetic NE555 model example; never qualify a real oscillator."""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from configs.pcbknowledge_intake_eval import expected_candidates  # noqa: E402
from pcbknowledge.git_native.intake import IntakeError, load_intake  # noqa: E402

PINS = {
    "knowledge/intake/ne555-timing-application-constraints.json":
        "bac46b80f8a5bbd63c0974457f793e1d5929aa46350944b1f06acea1af6ce3b5",
    "knowledge/intake/timer-reference-driver-pilot.json":
        "e2539fa657705a79dc6245cedb1b98c1a2eb0237e865deb7afa064a5167fe695",
    "knowledge/intake/vishay-crcw060310k0fkea-rating-constraints.json":
        "a8bb3d06470509605dee99d5b52f9854eac29a3c406781a7171a005505acb438",
    "knowledge/intake/kemet-c0603c104k5ractu-capacitance-constraints.json":
        "e4cb0113234ed90ed6f9ef7e2c32cad842d6f9b7648ac017b16b2cbbe9903a1b",
}
EXCLUDED_SOURCES = {"ti-tl431", "ti-uln2003a"}
LIMITATIONS = (
    "Fixed synthetic nominal steady-state Figure 6-5 model only; no user scenario input. "
    "Rational results are exact arithmetic on approximate decimal coefficients, not exact "
    "physical predictions. Initial tolerance, typical sensitivities, rated voltage and "
    "recommended operating ranges establish no hardware timing interval. No working "
    "resistor or capacitor is selected. Loading, leakage, bias, aging, startup, control, "
    "noise and model error remain unevaluated. PASS is regression status, not circuit "
    "qualification. Source original bytes were not rechecked; Agent review is not human review."
)


class AstableEvaluationError(ValueError):
    """Pinned evidence or fixed regression contract is unavailable."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _evidence(root: Path) -> dict:
    selected = [b for b in load_intake(root) if b["path"] in PINS]
    if {b["path"]: b["sha256"] for b in selected} != PINS:
        raise AstableEvaluationError("bound intake bytes missing or changed; independent review required")
    def candidates(command: str) -> list[dict]:
        return [v for _, v in sorted(expected_candidates(selected, command).items())
                if v["source"]["id"] not in EXCLUDED_SOURCES]
    facts, issues = candidates("search"), candidates("issues")
    for item in facts + issues:
        if item["canonical"] is not False or item["evidence_verification"] != "NOT_LOCALLY_VERIFIED":
            raise AstableEvaluationError("source status differs")
    model = next(item["fact"] for item in facts if item["fact"]["id"] == "timer-app-03")
    if model["value"] != {
        "tH_s": "0.693 * (RA + RB) * C", "tL_s": "0.693 * RB * C",
        "period_s": "0.693 * (RA + 2 * RB) * C",
        "frequency_Hz": "1.44 / ((RA + 2 * RB) * C)",
        "output_driver_duty_low_fraction": "RB / (RA + 2 * RB)",
        "output_waveform_duty_high_fraction": "(RA + RB) / (RA + 2 * RB)",
        "distortion_guidance_max_frequency_Hz": 100000,
    }:
        raise AstableEvaluationError("reviewed model equations differ")
    return {"files": dict(PINS), "facts": facts, "issues": issues,
            "canonical": False, "human_reviewed": False,
            "evidence_verification": "NOT_LOCALLY_VERIFIED"}


def _inputs() -> dict:
    return {"manufacturer": "Texas Instruments", "device": "NE555DR",
            "package": "D, 8-pin SOIC", "revision": "SLFS022K",
            "topology": "Figure 6-5", "state": "nominal_steady_state",
            "reset": "valid", "control": "nominal_thresholds",
            "component_basis": "synthetic_constant_model_values",
            "RA_Ohm": "10000", "RB_Ohm": "10000", "C_F": "0.0000001",
            "VCC_V": "5", "TA_C": "25"}


def _result(nominal: dict | None = None, unknowns: list | None = None) -> dict:
    return {"outcome": "NOMINAL_APPROXIMATE_MODEL" if nominal is not None else "NOT_EVALUABLE",
            "nominal": nominal, "unknowns": unknowns or [],
            "hardware_timing_interval": None, "hardware_accuracy": "UNKNOWN",
            "working_component_selection": "NOT_ESTABLISHED",
            "circuit_qualification": "NOT_ESTABLISHED"}


def _calculate(inputs: dict) -> dict:
    """Internal fixed-fixture arithmetic; deliberately not a generic circuit API."""
    fixed = _inputs()
    if inputs != fixed:
        return _result(unknowns=["outside_fixed_synthetic_scope"])
    ra, rb, c = (F(inputs[key]) for key in ("RA_Ohm", "RB_Ohm", "C_F"))
    kt, kf = F("0.693"), F("1.44")
    high, low = kt * (ra + rb) * c, kt * rb * c
    period = high + low
    return _result({
        "high_time_s": str(high), "low_time_s": str(low), "period_s": str(period),
        "frequency_from_rounded_formula_Hz": str(kf / ((ra + 2 * rb) * c)),
        "reciprocal_rounded_period_Hz": str(1 / period),
        "high_waveform_fraction": str(high / period),
        "low_driver_fraction": str(low / period),
        "rounded_coefficient_product": str(kt * kf),
        "arithmetic_scope": "EXACT_RATIONAL_ON_APPROXIMATE_MODEL_COEFFICIENTS",
    })


def _scenarios() -> list[tuple[str, dict, dict]]:
    # Independent literal oracle: never derive expected numbers through _calculate.
    expected = _result({
        "high_time_s": "693/500000", "low_time_s": "693/1000000", "period_s": "2079/1000000",
        "frequency_from_rounded_formula_Hz": "480", "reciprocal_rounded_period_Hz": "1000000/2079",
        "high_waveform_fraction": "2/3", "low_driver_fraction": "1/3",
        "rounded_coefficient_product": "6237/6250",
        "arithmetic_scope": "EXACT_RATIONAL_ON_APPROXIMATE_MODEL_COEFFICIENTS",
    })
    cases = [("document_example", _inputs(), expected)]
    for name, change in (
        ("cmos_substitution", {"device": "TLC555"}),
        ("diode_topology", {"topology": "diode_variant"}),
        ("startup", {"state": "startup"}),
        ("altered_control", {"control": "external_bias"}),
        ("reset_unknown", {"reset": None}),
        ("initial_tolerance_is_not_operating_C", {"component_basis": "nominal_plus_initial_tolerance"}),
        ("missing_C", {"C_F": None}),
        ("hot_operation", {"TA_C": "70"}),
        ("typical_sensitivity_is_not_error_bound", {"maximum_error_percent": "0.3"}),
    ):
        cases.append((name, {**_inputs(), **change}, _result(unknowns=["outside_fixed_synthetic_scope"])))
    return copy.deepcopy(cases)


def evaluate(root: Path) -> dict:
    evidence = _evidence(root)
    cases = []
    for name, inputs, expected in _scenarios():
        actual = _calculate(inputs)
        cases.append({"id": name, "synthetic_inputs": inputs, "expected": expected,
                      "actual": actual, "passed": _json(actual) == _json(expected)})
    if _json(_evidence(root)) != _json(evidence):
        raise AstableEvaluationError("bound evidence changed during evaluation")
    return {"format": "pcbknowledge-ne555-fixed-astable-eval-v1",
            "evaluation_status": "PASS" if all(c["passed"] for c in cases) else "FAIL",
            "case_count": len(cases), "cases": cases, "evidence": evidence,
            "evidence_sha256": hashlib.sha256(_json(evidence).encode()).hexdigest(),
            "limitations": LIMITATIONS, "circuit_qualification": "NOT_ESTABLISHED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--repo", type=Path, required=True, help="explicit intake workspace")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.repo.resolve())
        print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
        return 0 if report["evaluation_status"] == "PASS" else 1
    except (AstableEvaluationError, IntakeError, OSError, ValueError) as error:
        print(f"NE555 fixed astable evaluation: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
