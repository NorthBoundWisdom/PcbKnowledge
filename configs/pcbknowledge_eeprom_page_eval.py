#!/usr/bin/env python3
"""Evaluate fixed synthetic EEPROM transaction geometry, never perform device I/O."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from configs.pcbknowledge_intake_eval import expected_candidates  # noqa: E402
from pcbknowledge.git_native.intake import IntakeError, load_intake  # noqa: E402

BATCH = "knowledge/intake/24lc256-write-transaction-constraints.json"
PIN = "dcaa8eafd786aeeb42bc7871bfeb245511ea54f19cbef5be688e3abd165a532f"
IDENTITY = {"manufacturer": "Microchip Technology", "device": "24LC256-I/SN",
            "package": "SN, 8-lead SOIC", "revision": "DS20001203Y"}
LIMITATIONS = (
    "Fixed synthetic page geometry only; no user input, driver, emulator, bus I/O or hardware evidence. "
    "Atomic rejection describes this planner, not EEPROM power-fail atomicity. Address-pin states, "
    "controller convention and valid WP-high sampling are assumptions when supplied, not measured. "
    "A condition-specific 5 ms internal write-cycle maximum excludes serial transfer and is not "
    "a prescribed fixed delay. ACK readiness is not data verification. WP/supply timing, persistence, "
    "readback integrity and lifetime remain unqualified. Source original bytes were not rechecked; "
    "Agent review is not human approval. PASS is regression status only."
)


class PageEvaluationError(ValueError):
    """Pinned metadata or the fixed regression contract is unavailable."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _evidence(root: Path) -> dict:
    selected = [b for b in load_intake(root) if b["path"] == BATCH]
    if len(selected) != 1 or selected[0]["sha256"] != PIN:
        raise PageEvaluationError("bound intake bytes missing or changed; independent review required")
    facts = [v for _, v in sorted(expected_candidates(selected, "search").items())]
    issues = [v for _, v in sorted(expected_candidates(selected, "issues").items())]
    if [f["fact"]["id"] for f in facts] != [f"eeprom-app-{n:02}" for n in range(1, 8)]:
        raise PageEvaluationError("complete seven-fact scope required")
    if {i["source_issue"]["id"] for i in issues} != {
        "eeprom-app-transaction-unknown", "eeprom-app-persistence-unknown", "eeprom-app-lifetime-unknown"
    }:
        raise PageEvaluationError("complete unresolved warnings required")
    for item in facts + issues:
        if (any(item["source"].get(k) != v for k, v in IDENTITY.items())
                or item["canonical"] is not False
                or item["evidence_verification"] != "NOT_LOCALLY_VERIFIED"):
            raise PageEvaluationError("bound identity or verification status differs")
    if facts[1]["fact"]["value"]["page_bytes"] != 64:
        raise PageEvaluationError("reviewed page geometry differs")
    return {"files": {BATCH: PIN}, "facts": facts, "issues": issues,
            "canonical": False, "human_reviewed": False,
            "evidence_verification": "NOT_LOCALLY_VERIFIED"}


def _inputs(start: int = 62, length: int = 4) -> dict:
    return {**IDENTITY, "model": "page_write_geometry", "start": start, "length": length,
            "A2_A1_A0": [0, 0, 0], "controller_convention": "seven_bit",
            "WP_at_valid_Stop_window": None, "matching_write_poll_ACK": None}


def _empty() -> dict:
    return {"outcome": "NOT_EVALUABLE", "reason": None, "transactions": [],
            "address_roles": None, "inter_transaction_requirement": None,
            "programming": "NOT_ESTABLISHED",
            "readiness": "NOT_OBSERVED", "data_verified": False,
            "WP_timing_qualified": False, "supply_qualified": False,
            "persistence_qualified": False, "lifetime_qualified": False,
            "circuit_qualification": "NOT_ESTABLISHED"}


def _calculate(inputs: dict) -> dict:
    """Internal pure synthetic planning; validates the whole request before splitting."""
    result = _empty()
    if not isinstance(inputs, dict) or set(inputs) != set(_inputs()):
        result["reason"] = "missing_or_extra_input"
        return result
    if any(inputs[k] != v for k, v in IDENTITY.items()) or inputs["model"] != "page_write_geometry":
        result["reason"] = "unsupported_identity_or_model"
        return result
    start, length = inputs["start"], inputs["length"]
    if (type(start) is not int or type(length) is not int or start < 0 or length <= 0
            or start >= 32768 or length > 32768 - start):
        result["reason"] = "outside_positive_in_device_geometry"
        return result
    pins = inputs["A2_A1_A0"]
    if pins is not None and (not isinstance(pins, list) or len(pins) != 3
                            or any(type(bit) is not int or bit not in (0, 1) for bit in pins)):
        result["reason"] = "invalid_address_pin_assumption"
        return result
    if (inputs["controller_convention"] not in (None, "seven_bit", "write_control_byte")
            or inputs["WP_at_valid_Stop_window"] not in (None, "HIGH", "LOW")
            or inputs["matching_write_poll_ACK"] not in (None, "READY")):
        result["reason"] = "unsupported_protocol_assumption"
        return result
    target = None if pins is None else 0x50 | (pins[0] << 2) | (pins[1] << 1) | pins[2]
    write = None if target is None else target << 1
    read = None if target is None else (target << 1) | 1
    convention = inputs["controller_convention"]
    result["address_roles"] = {
        "seven_bit_target": target, "write_control_byte": write, "read_control_byte": read,
        "controller_argument": target if convention == "seven_bit" else write if convention == "write_control_byte" else None,
        "controller_convention": convention, "word_address_order": "HIGH_BYTE_FIRST",
    }
    offset = 0
    while offset < length:
        address = start + offset
        size = min(length - offset, 64 - address % 64)
        result["transactions"].append({"start": address, "data_offset": offset, "length": size,
                                      "word_address_bytes": [address >> 8, address & 0xFF]})
        offset += size
    result["outcome"] = "GEOMETRY_PLAN_ONLY"
    result["inter_transaction_requirement"] = "SEPARATE_STOP_AND_MATCHING_DEVICE_READINESS_CHECK"
    if inputs["WP_at_valid_Stop_window"] == "HIGH":
        result["programming"] = "NO_PROGRAMMING_UNDER_VALID_WP_HIGH_ASSUMPTION"
    if inputs["matching_write_poll_ACK"] == "READY":
        result["readiness"] = "NEXT_COMMAND_ALLOWED_UNDER_MATCHING_POLL_ASSUMPTION"
    return result


def _expected(transactions: list | None = None, reason: str | None = None) -> dict:
    # Literal, independent oracle shape: no call to the implementation result builder.
    return {"outcome": "NOT_EVALUABLE" if transactions is None else "GEOMETRY_PLAN_ONLY",
            "reason": reason, "transactions": transactions or [],
            "address_roles": None if transactions is None else {
                "seven_bit_target": 80, "write_control_byte": 160, "read_control_byte": 161,
                "controller_argument": 80, "controller_convention": "seven_bit",
                "word_address_order": "HIGH_BYTE_FIRST"},
            "inter_transaction_requirement": None if transactions is None else "SEPARATE_STOP_AND_MATCHING_DEVICE_READINESS_CHECK",
            "programming": "NOT_ESTABLISHED", "readiness": "NOT_OBSERVED", "data_verified": False,
            "WP_timing_qualified": False, "supply_qualified": False, "persistence_qualified": False,
            "lifetime_qualified": False, "circuit_qualification": "NOT_ESTABLISHED"}


def _scenarios() -> list[tuple[str, dict, dict]]:
    # These tuples are literal expected (address, data offset, length, high byte, low byte).
    cases = []
    for name, start, length, rows in (
        ("cross_page", 62, 4, [(62, 0, 2, 0, 62), (64, 2, 2, 0, 64)]),
        ("aligned_page", 64, 64, [(64, 0, 64, 0, 64)]),
        ("three_chunks", 63, 66, [(63, 0, 1, 0, 63), (64, 1, 64, 0, 64), (128, 65, 1, 0, 128)]),
        ("last_byte", 32767, 1, [(32767, 0, 1, 127, 255)]),
        ("last_page", 32704, 64, [(32704, 0, 64, 127, 192)]),
    ):
        expected = _expected([{"start": a, "data_offset": o, "length": n, "word_address_bytes": [h, l]}
                              for a, o, n, h, l in rows])
        cases.append((name, _inputs(start, length), expected))
    base_expected = copy.deepcopy(cases[0][2])
    for name, changes, expected_changes in (
        ("unknown_pins", {"A2_A1_A0": None}, {"address_roles": {
            "seven_bit_target": None, "write_control_byte": None, "read_control_byte": None,
            "controller_argument": None, "controller_convention": "seven_bit", "word_address_order": "HIGH_BYTE_FIRST"}}),
        ("unknown_API", {"controller_convention": None}, {"address_roles": {
            "seven_bit_target": 80, "write_control_byte": 160, "read_control_byte": 161,
            "controller_argument": None, "controller_convention": None, "word_address_order": "HIGH_BYTE_FIRST"}}),
        ("write_control_API", {"A2_A1_A0": [1, 0, 1], "controller_convention": "write_control_byte"}, {"address_roles": {
            "seven_bit_target": 85, "write_control_byte": 170, "read_control_byte": 171,
            "controller_argument": 170, "controller_convention": "write_control_byte", "word_address_order": "HIGH_BYTE_FIRST"}}),
        ("WP_high_ACK", {"WP_at_valid_Stop_window": "HIGH", "matching_write_poll_ACK": "READY"}, {
            "programming": "NO_PROGRAMMING_UNDER_VALID_WP_HIGH_ASSUMPTION",
            "readiness": "NEXT_COMMAND_ALLOWED_UNDER_MATCHING_POLL_ASSUMPTION"}),
        ("ACK_not_verification", {"WP_at_valid_Stop_window": "LOW", "matching_write_poll_ACK": "READY"}, {
            "readiness": "NEXT_COMMAND_ALLOWED_UNDER_MATCHING_POLL_ASSUMPTION"}),
    ):
        cases.append((name, {**_inputs(), **changes}, {**copy.deepcopy(base_expected), **expected_changes}))
    for name, changes, reason in (
        ("device_end_reject_all", {"start": 32767, "length": 2}, "outside_positive_in_device_geometry"),
        ("zero_length_local_scope", {"length": 0}, "outside_positive_in_device_geometry"),
        ("negative_start", {"start": -1}, "outside_positive_in_device_geometry"),
        ("bool_not_integer", {"length": True}, "outside_positive_in_device_geometry"),
        ("missing_length", {"length": None}, "outside_positive_in_device_geometry"),
        ("wrong_model", {"model": "sequential_read"}, "unsupported_identity_or_model"),
    ):
        cases.append((name, {**_inputs(), **changes}, _expected(reason=reason)))
    return copy.deepcopy(cases)


def _wrap_counterexample() -> dict:
    start = 62
    return {"hypothetical_unsplit_addresses": [(start & ~63) | ((start + i) & 63) for i in range(4)],
            "intended_addresses": [start + i for i in range(4)],
            "scope": "ADDRESS_COUNTER_MODEL_NOT_PROGRAMMING_EVIDENCE"}


def evaluate(root: Path) -> dict:
    evidence = _evidence(root)
    cases = []
    for name, inputs, expected in _scenarios():
        actual = _calculate(inputs)
        cases.append({"id": name, "synthetic_inputs": inputs, "expected": expected,
                      "actual": actual, "passed": _json(actual) == _json(expected)})
    expected_wrap = {"hypothetical_unsplit_addresses": [62, 63, 0, 1],
                     "intended_addresses": [62, 63, 64, 65],
                     "scope": "ADDRESS_COUNTER_MODEL_NOT_PROGRAMMING_EVIDENCE"}
    actual_wrap = _wrap_counterexample()
    cases.append({"id": "unsplit_wrap_counterexample", "expected": expected_wrap,
                  "actual": actual_wrap, "passed": _json(actual_wrap) == _json(expected_wrap)})
    if _json(_evidence(root)) != _json(evidence):
        raise PageEvaluationError("bound evidence changed during evaluation")
    return {"format": "pcbknowledge-eeprom-fixed-page-eval-v1",
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
    except (PageEvaluationError, IntakeError, OSError, ValueError) as error:
        print(f"EEPROM fixed page evaluation: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
