"""Iter 70 — Wrap-up: Interest Expense group filter, Schedule CSV export,
pytest-rerunfailures infra.

Backend-side we can only verify (1) the /expense-categories groups payload
correctly labels "Financial Costs" (used by the frontend KPI split) and (2)
the Interest Expense (Capital) category exists.

Schedule CSV export is a pure frontend copy-to-clipboard flow — no backend
work needed. The frontend button is data-testid="schedule-copy-csv".

pytest-rerunfailures is verified live by pytest.ini presence + plugin load
in `--collect-only` output.
"""
import os
import pytest
import requests

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pawnly-pro.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN = {"email": "admin@fatinpenhores.tl", "password": "admin123"}


@pytest.fixture(scope="module")
def s():
    session = requests.Session()
    r = session.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200
    return session


def test_expense_categories_expose_financial_costs_group(s):
    """Frontend KPI split needs 'Financial Costs' as a distinct group so it
    can bucket Operating vs Financial expenses."""
    d = s.get(f"{API}/expense-categories", timeout=15).json()
    labels = {g["label"] for g in d.get("groups", [])}
    assert "Financial Costs" in labels
    fin_group = next(g for g in d["groups"] if g["label"] == "Financial Costs")
    assert "Interest Expense (Capital)" in fin_group["items"]


def test_pytest_rerunfailures_configured():
    """pytest.ini must configure rerunfailures so preview-URL timeouts
    self-heal in CI without polluting real failure reports."""
    import pathlib
    import importlib
    ini = pathlib.Path("/app/backend/pytest.ini").read_text()
    assert "--reruns" in ini, "pytest.ini must configure --reruns"
    assert "--only-rerun" in ini, "pytest.ini must scope --only-rerun to network errors"
    # Confirm the plugin is installed
    plugin = importlib.import_module("pytest_rerunfailures")
    assert plugin is not None, "pytest-rerunfailures plugin missing"
