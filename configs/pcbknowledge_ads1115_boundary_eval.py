#!/usr/bin/env python3
"""Evaluate fixed synthetic ADS1115 pin-rail examples, never a real circuit.

No user scenario input is accepted. PASS describes this regression evaluation,
not electrical safety, source verification, acquisition accuracy or qualification.
"""
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

PINS = {
    "knowledge/intake/interface-ic-pilot.json":
        "3738281495ba3e2fa1120e0f501239ab1608c6ce0781e7dc4b5c0f2b32b7ab55",
    "knowledge/intake/ads1115-input-interface-constraints.json":
        "746353eeab5df619970c2cc2767a440b7fe92e5914fa42577208fdb9e233b5e7",
}
RAIL_REF = "knowledge/intake/interface-ic-pilot.json#b003-ti-ads1115-e-07"
APP_PATH = "knowledge/intake/ads1115-input-interface-constraints.json"
APP_SOURCE = "ads1115-app-ti-e-dgs"
PDF_SHA = "eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834"
IDENTITY = {"manufacturer": "Texas Instruments", "device": "ADS1115IDGSR",
            "package": "DGS, 10-pin VSSOP", "revision": "SBAS444E"}
WARNINGS = ("ads1115-app-controller-uncertainty", "ads1115-app-range-uncertainty",
            "ads1115-app-sensor-uncertainty")
LIMITATIONS = (
    "Fixed synthetic steady powered-state examples at VDD=3.3 V, GND=0 V and TA=25 C only. "
    "Pin-rail comparison is not a supply, differential/PGA, stress, accuracy, settling, "
    "interface, transient, sequencing or whole-circuit qualification. Source original bytes "
    "were not rechecked; recorded Agent review is not human approval."
)


class BoundaryEvaluationError(ValueError):
    """Pinned evidence or regression contract is unavailable."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _evidence(root: Path) -> dict:
    batches = load_intake(root)
    selected = [batch for batch in batches if batch["path"] in PINS]
    if {batch["path"]: batch["sha256"] for batch in selected} != PINS:
        raise BoundaryEvaluationError("bound intake bytes are missing or changed; independent review required")
    candidates = expected_candidates(selected, "search")
    refs = [RAIL_REF] + [f"{APP_PATH}#ads1115-app-{n:02}" for n in range(1, 10)]
    if any(ref not in candidates for ref in refs):
        raise BoundaryEvaluationError("required source-bound facts are absent")
    facts = [candidates[ref] for ref in refs]
    rail = facts[0]
    if (rail["fact"]["kind"] != "recommended_operating"
            or rail["fact"]["value"] != {"min_reference": "GND", "max_reference": "VDD"}
            or rail["fact"]["unit"] != "V"):
        raise BoundaryEvaluationError("rail semantics are not the reviewed recommended pin limits")
    for candidate in facts:
        if (any(candidate["source"].get(k) != v for k, v in IDENTITY.items())
                or candidate["source"].get("pdf_sha256") != PDF_SHA
                or candidate["canonical"] is not False
                or candidate["evidence_verification"] != "NOT_LOCALLY_VERIFIED"):
            raise BoundaryEvaluationError("source identity or evidence status differs")
    issues = expected_candidates(selected, "issues")
    issue_refs = [f"{APP_PATH}#{identifier}" for identifier in WARNINGS]
    if any(ref not in issues for ref in issue_refs):
        raise BoundaryEvaluationError("required unresolved application warnings are absent")
    # Full candidates retain original source, fact, conditions, anchors and all
    # source-local issues; this is not a reduced ID-only or numeric evidence view.
    return {"files": dict(PINS), "facts": facts,
            "issues": [issues[ref] for ref in issue_refs],
            "canonical": False, "human_reviewed": False,
            "evidence_verification": "NOT_LOCALLY_VERIFIED"}


def _number(value: object) -> Fraction | None:
    # Decimal strings avoid float rounding and reject bool, NaN, infinity and
    # executable expressions. This is an internal fixed-fixture parser only.
    if not isinstance(value, str) or len(value) > 40:
        return None
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None:
        return None
    return Fraction(value)


def _compare_pins(scenario: dict) -> dict:
    """One narrow predicate for fixed fixtures; not a public design-check API."""
    result = {"outcome": "NOT_EVALUABLE", "violations": [], "unknowns": [],
              "circuit_qualification": "NOT_ESTABLISHED"}
    if any(scenario.get(k) != v for k, v in IDENTITY.items()):
        result["unknowns"] = ["unsupported_identity"]
        return result
    if any(scenario.get(k) != v for k, v in
           {"vdd_V": "3.3", "gnd_V": "0", "ambient_C": "25",
            "power_state": "steady_powered", "pga_magnitude_V": "4.096"}.items()):
        result["unknowns"] = ["missing_or_out_of_scope_operating_assumptions"]
        return result
    for name in ("ainp_V", "ainn_V"):
        interval = scenario.get(name)
        if not isinstance(interval, list) or len(interval) != 2:
            result["unknowns"].append(name)
            continue
        low, high = map(_number, interval)
        if low is None or high is None or low > high:
            result["unknowns"].append(name)
            continue
        if low < Fraction(0):
            result["violations"].append(name + ":BELOW_GND")
        if high > Fraction(33, 10):
            result["violations"].append(name + ":ABOVE_VDD")
    # A known violation remains a violation even when the other pin is unknown.
    # Unknowns are never erased, and neither result can qualify a circuit.
    if result["violations"]:
        result["outcome"] = "RECOMMENDED_PIN_RAIL_EXCEEDED"
    elif not result["unknowns"]:
        result["outcome"] = "NO_PIN_RAIL_VIOLATION_IN_STATED_INTERVALS"
    return result


def _scenarios() -> list[tuple[str, dict, str, list[str], list[str]]]:
    base = {**IDENTITY, "vdd_V": "3.3", "gnd_V": "0", "ambient_C": "25",
            "power_state": "steady_powered", "pga_magnitude_V": "4.096",
            "ainp_V": ["0", "3"], "ainn_V": ["0", "0"]}
    within = "NO_PIN_RAIL_VIOLATION_IN_STATED_INTERVALS"
    outside = "RECOMMENDED_PIN_RAIL_EXCEEDED"
    fixtures = [
        ("report_4V_endpoint", {"ainp_V": ["0", "4"]}, outside, ["ainp_V:ABOVE_VDD"], []),
        ("same_evidence_3V_endpoint", {}, within, [], []),
        ("small_difference_upper_common_mode", {"ainp_V": ["4", "4"], "ainn_V": ["3", "3"]},
         outside, ["ainp_V:ABOVE_VDD"], []),
        ("small_difference_negative_pin", {"ainp_V": ["1", "1"], "ainn_V": ["-0.1", "-0.1"]},
         outside, ["ainn_V:BELOW_GND"], []),
        ("inclusive_both_rails", {"ainp_V": ["0", "3.3"], "ainn_V": ["0", "3.3"]}, within, [], []),
        ("exactly_above_upper", {"ainp_V": ["0", "3.30000000000000000001"]},
         outside, ["ainp_V:ABOVE_VDD"], []),
        ("exactly_below_lower", {"ainn_V": ["-0.00000000000000000001", "0"]},
         outside, ["ainn_V:BELOW_GND"], []),
        ("negative_difference_in_rails", {"ainp_V": ["0", "0"], "ainn_V": ["1", "1"]}, within, [], []),
        ("missing_pin", {"ainn_V": None}, "NOT_EVALUABLE", [], ["ainn_V"]),
        ("missing_supply", {"vdd_V": None}, "NOT_EVALUABLE", [],
         ["missing_or_out_of_scope_operating_assumptions"]),
        ("known_violation_other_pin_unknown", {"ainp_V": ["0", "4"], "ainn_V": None},
         outside, ["ainp_V:ABOVE_VDD"], ["ainn_V"]),
        ("wrong_package", {"package": "RUG, 10-pin X2QFN"}, "NOT_EVALUABLE", [], ["unsupported_identity"]),
        ("non_numeric_pin", {"ainp_V": ["0", "unknown"]}, "NOT_EVALUABLE", [], ["ainp_V"]),
        ("reversed_interval", {"ainp_V": ["3", "0"]}, "NOT_EVALUABLE", [], ["ainp_V"]),
    ]
    return [(name, {**copy.deepcopy(base), **updates}, outcome, violations, unknowns)
            for name, updates, outcome, violations, unknowns in fixtures]


def evaluate(root: Path) -> dict:
    evidence = _evidence(root)
    results = []
    for name, scenario, outcome, violations, unknowns in _scenarios():
        actual = _compare_pins(scenario)
        expected = {"outcome": outcome, "violations": violations, "unknowns": unknowns,
                    "circuit_qualification": "NOT_ESTABLISHED"}
        results.append({"id": name, "synthetic_inputs": scenario, "expected": expected,
                        "actual": actual, "passed": _json(actual) == _json(expected)})
    if _json(_evidence(root)) != _json(evidence):
        raise BoundaryEvaluationError("bound evidence changed during evaluation")
    return {"format": "pcbknowledge-ads1115-fixed-boundary-eval-v1",
            "evaluation_status": "PASS" if all(x["passed"] for x in results) else "FAIL",
            "case_count": len(results), "cases": results, "evidence": evidence,
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
    except (BoundaryEvaluationError, IntakeError, OSError, ValueError) as error:
        print(f"ADS1115 fixed boundary evaluation: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
