"""
test_suite.py — dynamically generated tests from test_cases.yaml.

pytest discovers test functions generated from the YAML config.
Each isolated test and each flow test becomes a separate pytest test case.
"""

import os
import sys
import pytest
import yaml

# Add parent directory to path so utils imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.test_runner import load_test_cases, run_isolated_test, run_flow_test


# Load test cases at module level for parametrize
_test_cases = load_test_cases()
_isolated = _test_cases.get("isolated", [])
_flows = _test_cases.get("flows", [])


# ---------------------------------------------------------------------------
# Isolated tests — one pytest test per YAML entry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "test_case",
    _isolated,
    ids=[tc["name"] for tc in _isolated],
)
def test_isolated(test_case, your_phone, clean_contact):
    result = run_isolated_test(test_case, your_phone, clean_contact)
    assert result["passed"], (
        f"[{test_case['name']}] FAILED\n"
        f"  Respond: {result['respond_detail']}\n"
        f"  Odoo: {result['odoo_detail']}\n"
        f"  AI Notes: {result['ai_notes']}\n"
        f"  Reply: {result['actual_reply'][:300]}"
    )


# ---------------------------------------------------------------------------
# Flow tests — one pytest test per YAML flow entry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "test_case",
    _flows,
    ids=[tc["name"] for tc in _flows],
)
def test_flow(test_case, your_phone, clean_contact, cfg):
    result = run_flow_test(test_case, your_phone, clean_contact)
    assert result["passed"], (
        f"[{test_case['name']}] FAILED\n"
        f"  Respond: {result['respond_detail']}\n"
        f"  Odoo: {result['odoo_detail']}\n"
        f"  AI Notes: {result['ai_notes']}\n"
        f"  Reply: {result['actual_reply'][:300]}"
    )
