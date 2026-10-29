#!/usr/bin/env python3
"""Evaluate fixed synthetic INA219 register arithmetic, never perform device I/O."""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction as F
import re
import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from configs.pcbknowledge_intake_eval import expected_candidates  # noqa: E402
from pcbknowledge.git_native.intake import IntakeError, load_intake  # noqa: E402

BATCH = "knowledge/intake/ina219-measurement-calibration-constraints.json"
PIN = "9b5206cb30d221dffcb9b5b036a67e2ee623ea07f15ad43fca4de81d46d2e3cb"
IDENTITY = {"manufacturer": "Texas Instruments", "device": "INA219AIDCNR",
            "package": "DCN (SOT-23, 8 pins)", "revision": "SBOS448G"}
LIMITATIONS = (
    "Fixed synthetic register arithmetic only; no I/O, driver, state machine or user-input API. "
    "Shunt input is assumed correctly sign-extended for its PGA representation. Current and power "
    "codes are independently supplied, not predicted from shunt times CAL. Declared scale consistency "
    "is not ideal gain, physical accuracy, analog validity or a fresh coherent measurement. "
    "CNVR/OVF do not resolve the source readiness-wording conflict; a guaranteed readiness sequence "
    "remains BLOCKED. Original source bytes were not rechecked; no new source-access clearance."
)


class RegisterEvaluationError(ValueError):
    """Pinned metadata or the fixed regression contract is unavailable."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _evidence(root: Path) -> dict:
    selected = [b for b in load_intake(root) if b["path"] == BATCH]
    if len(selected) != 1 or selected[0]["sha256"] != PIN:
        raise RegisterEvaluationError("bound intake bytes missing or changed; independent review required")
    facts = [v for _, v in sorted(expected_candidates(selected, "search").items())]
    issues = [v for _, v in sorted(expected_candidates(selected, "issues").items())]
    if [f["fact"]["id"] for f in facts] != [f"monitor-app-{n:02}" for n in range(1, 9)]:
        raise RegisterEvaluationError("complete eight-fact scope required")
    if {i["source_issue"]["id"] for i in issues} != {
        "monitor-app-shunt-unknown", "monitor-app-calibration-freshness-unknown", "monitor-app-readiness-wording"
    }:
        raise RegisterEvaluationError("complete unresolved warnings required")
    for item in facts + issues:
        if (any(item["source"].get(k) != v for k, v in IDENTITY.items())
                or item["canonical"] is not False
                or item["evidence_verification"] != "NOT_LOCALLY_VERIFIED"):
            raise RegisterEvaluationError("bound identity or verification status differs")
    return {"files": {BATCH: PIN}, "facts": facts, "issues": issues,
            "canonical": False, "human_reviewed": False,
            "evidence_verification": "NOT_LOCALLY_VERIFIED"}


def _inputs() -> dict:
    return {**IDENTITY, "model": "independent_register_scale",
            "shunt_representation": "correctly_sign_extended_for_PGA",
            "shunt_register": 0xFF9C, "bus_register": 0x1F42,
            "current_register": 0xFF9C, "power_register": 250,
            "current_lsb_A": "0.001", "shunt_Ohm": "0.1", "actual_calibration": 408}


def _decimal(value: object) -> F | None:
    if (not isinstance(value, str) or len(value) > 40
            or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None):
        return None
    number = F(value)
    return number if number > 0 else None


def _signed(code: int) -> int:
    return code - 65536 if code & 32768 else code


def _calculate(inputs: dict) -> dict:
    result = {"outcome": "NOT_EVALUABLE", "reason": None, "raw": None,
              "calibration": None, "scaled": None, "scale_consistency": "NOT_ESTABLISHED",
              "physical_accuracy": "UNKNOWN", "analog_validity": "UNKNOWN",
              "freshness_and_coherence": "UNKNOWN", "readiness_sequence": "BLOCKED",
              "circuit_qualification": "NOT_ESTABLISHED"}
    if not isinstance(inputs, dict) or set(inputs) != set(_inputs()):
        result["reason"] = "missing_or_extra_input"
        return result
    if (any(inputs[k] != v for k, v in IDENTITY.items())
            or inputs["model"] != "independent_register_scale"
            or inputs["shunt_representation"] != "correctly_sign_extended_for_PGA"):
        result["reason"] = "unsupported_identity_model_or_shunt_representation"
        return result
    for key in ("shunt_register", "bus_register", "current_register", "power_register"):
        if type(inputs[key]) is not int or not 0 <= inputs[key] <= 65535:
            result["reason"] = "invalid_16bit_register"
            return result
    actual = inputs["actual_calibration"]
    if actual is not None and (type(actual) is not int or not 0 <= actual <= 65535 or actual & 1):
        result["reason"] = "invalid_actual_calibration"
        return result
    bus = inputs["bus_register"]
    result["raw"] = {"shunt_uV": _signed(inputs["shunt_register"]) * 10,
                     "bus_mV": (bus >> 3) * 4, "CNVR": (bus >> 1) & 1, "OVF": bus & 1}
    result["outcome"] = "RAW_REGISTER_ARITHMETIC_ONLY"
    lsb, resistance = _decimal(inputs["current_lsb_A"]), _decimal(inputs["shunt_Ohm"])
    if lsb is None or resistance is None:
        result["reason"] = "missing_or_invalid_positive_scale_inputs"
        return result
    candidate = F("0.04096") / (lsb * resistance)
    truncated = int(candidate)
    # Reject before clearing FS0; overflow is not repaired through a bit mask.
    if not 1 <= truncated <= 65535:
        result["reason"] = "calibration_outside_representable_range"
        return result
    effective = truncated - truncated % 2
    result["calibration"] = {"candidate_exact": str(candidate), "truncated": truncated,
                             "effective_FS0_zero": effective, "actual": actual,
                             "declared_current_lsb_A": str(lsb), "declared_power_lsb_W": str(20 * lsb)}
    if effective == 0:
        result["reason"] = "effective_calibration_zero"
    elif actual is None:
        result["reason"] = "actual_calibration_unknown"
    elif actual == 0:
        result["reason"] = "calibration_zero_not_zero_load"
    elif actual != effective:
        result["reason"] = "actual_calibration_does_not_match_plan"
    elif bus & 1:
        result["reason"] = "computed_arithmetic_overflow"
    else:
        result["scaled"] = {"current_A_exact": str(_signed(inputs["current_register"]) * lsb),
                            "power_W_exact": str(inputs["power_register"] * 20 * lsb)}
        result["outcome"] = "CONDITIONAL_REGISTER_SCALING"
        result["scale_consistency"] = "DECLARED_SCALE_AND_SUPPLIED_CAL_MATCH_ONLY"
    return result


def _expected() -> dict:
    # Independent literal oracle, including all refusal/authority fields.
    return {"outcome": "CONDITIONAL_REGISTER_SCALING", "reason": None,
            "raw": {"shunt_uV": -1000, "bus_mV": 4000, "CNVR": 1, "OVF": 0},
            "calibration": {"candidate_exact": "2048/5", "truncated": 409, "effective_FS0_zero": 408,
                            "actual": 408, "declared_current_lsb_A": "1/1000", "declared_power_lsb_W": "1/50"},
            "scaled": {"current_A_exact": "-1/10", "power_W_exact": "5"},
            "scale_consistency": "DECLARED_SCALE_AND_SUPPLIED_CAL_MATCH_ONLY",
            "physical_accuracy": "UNKNOWN", "analog_validity": "UNKNOWN",
            "freshness_and_coherence": "UNKNOWN", "readiness_sequence": "BLOCKED",
            "circuit_qualification": "NOT_ESTABLISHED"}


def _scenarios() -> list[tuple[str, dict, dict]]:
    cases = [("nominal_independent_codes", _inputs(), _expected())]
    for name, changes, raw, scaled in (
        ("reserved_bit_excluded", {"bus_register": 0x1F46}, {"shunt_uV": -1000, "bus_mV": 4000, "CNVR": 1, "OVF": 0}, {"current_A_exact": "-1/10", "power_W_exact": "5"}),
        ("CNVR_zero_not_freshness", {"bus_register": 0x1F40}, {"shunt_uV": -1000, "bus_mV": 4000, "CNVR": 0, "OVF": 0}, {"current_A_exact": "-1/10", "power_W_exact": "5"}),
        ("signed_min_unsigned_max", {"current_register": 32768, "power_register": 65535}, {"shunt_uV": -1000, "bus_mV": 4000, "CNVR": 1, "OVF": 0}, {"current_A_exact": "-4096/125", "power_W_exact": "13107/10"}),
    ):
        expected = _expected(); expected.update(raw=raw, scaled=scaled)
        cases.append((name, {**_inputs(), **changes}, expected))
    for name, changes, reason in (
        ("OVF_suppresses_computed", {"bus_register": 0x1F43}, "computed_arithmetic_overflow"),
        ("reset_CAL_not_zero_load", {"actual_calibration": 0, "current_register": 0, "power_register": 0}, "calibration_zero_not_zero_load"),
        ("unknown_actual_CAL", {"actual_calibration": None}, "actual_calibration_unknown"),
        ("mismatched_actual_CAL", {"actual_calibration": 410}, "actual_calibration_does_not_match_plan"),
        ("missing_scale", {"current_lsb_A": None}, "missing_or_invalid_positive_scale_inputs"),
        ("CAL_overflow", {"current_lsb_A": "0.000001"}, "calibration_outside_representable_range"),
    ):
        expected = _expected(); expected.update(outcome="RAW_REGISTER_ARITHMETIC_ONLY", reason=reason,
                                               scaled=None, scale_consistency="NOT_ESTABLISHED")
        if name == "OVF_suppresses_computed": expected["raw"]["OVF"] = 1
        if name in ("missing_scale", "CAL_overflow"): expected["calibration"] = None
        else: expected["calibration"]["actual"] = changes.get("actual_calibration", 408)
        cases.append((name, {**_inputs(), **changes}, expected))
    return copy.deepcopy(cases)


def evaluate(root: Path) -> dict:
    evidence = _evidence(root)
    cases = []
    for name, inputs, expected in _scenarios():
        actual = _calculate(inputs)
        cases.append({"id": name, "synthetic_inputs": inputs, "expected": expected,
                      "actual": actual, "passed": _json(actual) == _json(expected)})
    if _json(_evidence(root)) != _json(evidence):
        raise RegisterEvaluationError("bound evidence changed during evaluation")
    return {"format": "pcbknowledge-ina219-fixed-register-eval-v1",
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
    except (RegisterEvaluationError, IntakeError, OSError, ValueError) as error:
        print(f"INA219 fixed register evaluation: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
