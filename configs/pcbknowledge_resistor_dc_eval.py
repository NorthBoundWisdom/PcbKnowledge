#!/usr/bin/env python3
"""Evaluate fixed synthetic resistor DC bounds, not user circuits or part suitability."""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from configs.pcbknowledge_intake_eval import expected_candidates  # noqa: E402
from pcbknowledge.git_native.intake import IntakeError, load_intake  # noqa: E402

BATCH = "knowledge/intake/vishay-crcw060310k0fkea-rating-constraints.json"
PIN = "a8bb3d06470509605dee99d5b52f9854eac29a3c406781a7171a005505acb438"
PDF_SHA = "3e595b731fa5916bcdce5b28cd76b5eb0b0b3cdd7da474c677173264748cdf5f"
SOURCE = "vishay-crcw060310k0fkea-20035-20260414"
IDENTITY = {"manufacturer": "Vishay", "device": "CRCW060310K0FKEA",
            "package": "0603 imperial (RR1608M metric)",
            "revision": "20035, Revision 14-Apr-2026"}
WARNINGS = tuple("vishay-crcw060310k0fkea-" + suffix for suffix in
                 ("application-inputs", "ordering-scope", "rights"))
LIMITATIONS = (
    "Fixed synthetic nonnegative steady-DC terminal-voltage examples with independently "
    "supplied positive operating resistance only. Initial nominal tolerance does not establish "
    "operating resistance. The standard P70 ratio is a numerical reference, not thermal "
    "headroom, permitted power or circuit qualification. Temperature, aging, mounting, "
    "pulse and AC behavior remain unevaluated. Source original bytes were not rechecked; "
    "Agent review is not human approval. No user scenario input is accepted."
)


class DcEvaluationError(ValueError):
    """Bound evidence or fixed regression contract is unavailable."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _evidence(root: Path) -> dict:
    selected = [batch for batch in load_intake(root) if batch["path"] == BATCH]
    if len(selected) != 1 or selected[0]["sha256"] != PIN:
        raise DcEvaluationError("bound intake bytes are missing or changed; independent review required")
    candidates = expected_candidates(selected, "search")
    refs = [f"{BATCH}#vishay-crcw060310k0fkea-rating-{n:02}" for n in range(1, 8)]
    if set(candidates) != set(refs):
        raise DcEvaluationError("complete seven-fact source scope is required")
    facts = [candidates[ref] for ref in refs]
    for candidate in facts:
        if (any(candidate["source"].get(k) != v for k, v in IDENTITY.items())
                or candidate["source"].get("id") != SOURCE
                or candidate["source"].get("pdf_sha256") != PDF_SHA
                or candidate["canonical"] is not False
                or candidate["evidence_verification"] != "NOT_LOCALLY_VERIFIED"):
            raise DcEvaluationError("source identity or evidence status differs")
    rating = facts[1]["fact"]
    if (rating["parameter"] != "standard_extended_rated_dissipation"
            or rating["kind"] != "electrical_characteristic"
            or rating["value"]["standard_P70_W"] != 0.1
            or rating["value"]["reference_ambient_C"] != 70):
        raise DcEvaluationError("standard numerical P70 reference differs")
    issues = expected_candidates(selected, "issues")
    issue_refs = [f"{BATCH}#{identifier}" for identifier in WARNINGS]
    if set(issues) != set(issue_refs):
        raise DcEvaluationError("complete unresolved source warnings are required")
    return {"files": {BATCH: PIN}, "facts": facts,
            "issues": [issues[ref] for ref in issue_refs], "canonical": False,
            "human_reviewed": False, "evidence_verification": "NOT_LOCALLY_VERIFIED"}


def _number(value: object) -> Fraction | None:
    if (not isinstance(value, str) or len(value) > 40
            or re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None):
        return None
    return Fraction(value)


def _interval(value: object) -> tuple[Fraction, Fraction] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    low, high = map(_number, value)
    if low is None or high is None or low > high:
        return None
    return low, high


def _outward_milli(value: Fraction, upper: bool) -> str:
    scaled = value * 1000 * 10**6
    n, d = scaled.numerator, scaled.denominator
    ticks = -(-n // d) if upper else n // d
    return f"{ticks // 10**6}.{ticks % 10**6:06d}"


def _calculate(scenario: dict, standard_p70: Fraction) -> dict:
    """Internal fixture calculation, not a public application-check API."""
    result = {"outcome": "NOT_EVALUABLE", "unknowns": [], "bounds": None,
              "circuit_qualification": "NOT_ESTABLISHED",
              "operating_resistance_guarantee": "NOT_ESTABLISHED",
              "thermal_qualification": "NOT_ESTABLISHED"}
    if any(scenario.get(k) != v for k, v in IDENTITY.items()):
        result["unknowns"] = ["unsupported_identity"]
        return result
    if scenario.get("waveform") != "steady_dc" or scenario.get("model") != "ohmic":
        result["unknowns"] = ["unsupported_or_missing_model"]
        return result
    if scenario.get("resistance_basis") != "independently_supplied_operating_interval":
        result["unknowns"] = ["operating_resistance_not_supplied"]
        return result
    voltage = _interval(scenario.get("terminal_voltage_V"))
    resistance = _interval(scenario.get("operating_resistance_Ohm"))
    if voltage is None or voltage[0] < 0:
        result["unknowns"].append("terminal_voltage_V")
    if resistance is None or resistance[0] <= 0:
        result["unknowns"].append("operating_resistance_Ohm")
    if result["unknowns"]:
        return result
    if standard_p70 != Fraction(1, 10):
        raise DcEvaluationError("only the reviewed standard reference is supported")
    vlo, vhi = voltage
    rlo, rhi = resistance
    current = (vlo / rhi, vhi / rlo)
    power = (vlo**2 / rhi, vhi**2 / rlo)
    result["bounds"] = {
        "current_A_exact": [str(x) for x in current],
        "power_W_exact": [str(x) for x in power],
        "current_mA_outward": [_outward_milli(x, i == 1) for i, x in enumerate(current)],
        "power_mW_outward": [_outward_milli(x, i == 1) for i, x in enumerate(power)],
        "upper_power_over_standard_P70_exact": str(power[1] / standard_p70),
        "reference_comparison_scope": "NUMERICAL_ONLY_NOT_ALLOWABLE_POWER",
    }
    result["outcome"] = "CONDITIONAL_DC_BOUNDS"
    return result


def _expected(bounds: dict | None = None, unknowns: list | None = None) -> dict:
    return {"outcome": "CONDITIONAL_DC_BOUNDS" if bounds is not None else "NOT_EVALUABLE",
            "unknowns": unknowns or [], "bounds": bounds,
            "circuit_qualification": "NOT_ESTABLISHED",
            "operating_resistance_guarantee": "NOT_ESTABLISHED",
            "thermal_qualification": "NOT_ESTABLISHED"}


def _scenarios() -> list[tuple[str, dict, dict]]:
    base = {**IDENTITY, "waveform": "steady_dc", "model": "ohmic",
            "resistance_basis": "independently_supplied_operating_interval",
            "terminal_voltage_V": ["4.75", "5.25"],
            "operating_resistance_Ohm": ["9800", "10200"]}
    nominal = {"current_A_exact": ["19/40800", "3/5600"],
               "power_W_exact": ["361/163200", "9/3200"],
               "current_mA_outward": ["0.465686", "0.535715"],
               "power_mW_outward": ["2.212009", "2.812500"],
               "upper_power_over_standard_P70_exact": "9/320",
               "reference_comparison_scope": "NUMERICAL_ONLY_NOT_ALLOWABLE_POWER"}
    zero = {"current_A_exact": ["0", "0"], "power_W_exact": ["0", "0"],
            "current_mA_outward": ["0.000000", "0.000000"],
            "power_mW_outward": ["0.000000", "0.000000"],
            "upper_power_over_standard_P70_exact": "0",
            "reference_comparison_scope": "NUMERICAL_ONLY_NOT_ALLOWABLE_POWER"}
    cases = [("document_example", {}, _expected(nominal)),
             ("zero_voltage_arithmetic_only", {"terminal_voltage_V": ["0", "0"]}, _expected(zero))]
    for name, changes, unknown in (
        ("missing_voltage", {"terminal_voltage_V": None}, "terminal_voltage_V"),
        ("missing_resistance", {"operating_resistance_Ohm": None}, "operating_resistance_Ohm"),
        ("initial_tolerance_only", {"resistance_basis": "nominal_plus_initial_tolerance"}, "operating_resistance_not_supplied"),
        ("zero_resistance", {"operating_resistance_Ohm": ["0", "1"]}, "operating_resistance_Ohm"),
        ("negative_resistance", {"operating_resistance_Ohm": ["-1", "1"]}, "operating_resistance_Ohm"),
        ("reversed_interval", {"terminal_voltage_V": ["5.25", "4.75"]}, "terminal_voltage_V"),
        ("negative_voltage_outside_example", {"terminal_voltage_V": ["-5", "0"]}, "terminal_voltage_V"),
        ("ac_rms_is_not_dc", {"waveform": "ac_rms"}, "unsupported_or_missing_model"),
        ("pulse_is_not_dc", {"waveform": "repeated_pulse"}, "unsupported_or_missing_model"),
        ("wrong_orderable", {"device": "CRCW06031K00FKEA"}, "unsupported_identity"),
        ("wrong_package", {"package": "0805"}, "unsupported_identity"),
        ("non_numeric", {"terminal_voltage_V": ["0", "NaN"]}, "terminal_voltage_V"),
    ):
        cases.append((name, changes, _expected(unknowns=[unknown])))
    return [(name, {**copy.deepcopy(base), **copy.deepcopy(changes)}, copy.deepcopy(expected))
            for name, changes, expected in cases]


def evaluate(root: Path) -> dict:
    evidence = _evidence(root)
    reference = Fraction(str(evidence["facts"][1]["fact"]["value"]["standard_P70_W"]))
    cases = []
    for name, inputs, expected in _scenarios():
        actual = _calculate(inputs, reference)
        cases.append({"id": name, "synthetic_inputs": inputs, "expected": expected,
                      "actual": actual, "passed": _json(actual) == _json(expected)})
    if _json(_evidence(root)) != _json(evidence):
        raise DcEvaluationError("bound evidence changed during evaluation")
    return {"format": "pcbknowledge-resistor-fixed-dc-eval-v1",
            "evaluation_status": "PASS" if all(case["passed"] for case in cases) else "FAIL",
            "case_count": len(cases), "cases": cases, "evidence": evidence,
            "evidence_sha256": hashlib.sha256(_json(evidence).encode("utf-8")).hexdigest(),
            "limitations": LIMITATIONS, "circuit_qualification": "NOT_ESTABLISHED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--repo", type=Path, required=True, help="explicit intake workspace")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.repo.resolve())
        print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
        return 0 if report["evaluation_status"] == "PASS" else 1
    except (DcEvaluationError, IntakeError, OSError, ValueError) as error:
        print(f"Resistor fixed DC evaluation: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
