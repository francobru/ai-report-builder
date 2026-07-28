"""Integration test: load PM_Consultas CSV → validate → compute KPIs.

Compares computed values against the known values from the May 2026 report.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data_loader.csv_loader import load_csv
from app.data_loader.validator import validate
from app.kpi_engine.calculator import compute_kpis
from app.plugins.contact_center.plugin import ContactCenterPlugin


CSV_PATH = Path("/mnt/user-data/uploads/PM_Consultas_may26.csv")

plugin = ContactCenterPlugin()
schema = plugin.get_schema()


def test_csv_loads_successfully():
    df = load_csv(CSV_PATH, schema=schema)
    assert len(df) > 0, "CSV should have rows after removing total"
    assert "TOTALCALLS" in df.columns
    assert "TRANSFER" in df.columns
    print(f"  ✓ Loaded {len(df)} rows")
    print(f"  ✓ Columns: {list(df.columns)}")


def test_total_row_removed():
    df = load_csv(CSV_PATH, schema=schema)
    first_col = df.columns[0]
    has_total = df[first_col].astype(str).str.lower().str.startswith("total").any()
    assert not has_total, "Total row should be removed"
    print("  ✓ Total row removed correctly")


def test_dates_parsed():
    df = load_csv(CSV_PATH, schema=schema)
    assert "date" in df.columns
    valid_dates = df["date"].dropna()
    assert len(valid_dates) == len(df), f"All dates should parse, got {len(valid_dates)}/{len(df)}"
    print(f"  ✓ Date range: {valid_dates.min().date()} → {valid_dates.max().date()}")


def test_validation_passes():
    df = load_csv(CSV_PATH, schema=schema)
    result = validate(df, schema, source_name="PM_Consultas_may26")
    assert result.is_valid, f"Validation failed: {result.errors}"
    print(f"  ✓ Validation passed: {result.summary}")
    if result.warnings:
        for w in result.warnings:
            print(f"    ⚠ {w}")


def test_kpis_match_report():
    """Verify computed KPIs match the PDF report values for PM Consultas."""
    df = load_csv(CSV_PATH, schema=schema)
    kpis = compute_kpis(df, plugin.get_kpis())

    # Expected values from page 15 of the report (habilidad PM Consultas)
    expected = {
        "recibidas": 8646,
        "atendidas": 7064,
        "nivel_atencion": 81.70,
    }

    print("\n  KPI Results vs Expected:")
    for kpi_id, expected_val in expected.items():
        actual = kpis[kpi_id]["value"]
        match = "✓" if abs(actual - expected_val) < 1 else "✗"
        print(f"    {match} {kpis[kpi_id]['label']}: {kpis[kpi_id]['formatted']} "
              f"(expected ≈{expected_val})")
        assert abs(actual - expected_val) < 1, (
            f"{kpi_id}: expected ~{expected_val}, got {actual}"
        )

    # Print all KPIs
    print("\n  All KPIs:")
    for kpi_id, data in kpis.items():
        unit = data["unit"]
        print(f"    {data['label']}: {data['formatted']}{' ' + unit if unit and unit not in data['formatted'] else ''}")


if __name__ == "__main__":
    print("=" * 60)
    print("Integration Test: PM_Consultas_may26.csv")
    print("=" * 60)

    tests = [
        test_csv_loads_successfully,
        test_total_row_removed,
        test_dates_parsed,
        test_validation_passes,
        test_kpis_match_report,
    ]

    passed = 0
    failed = 0
    for test_func in tests:
        print(f"\n▸ {test_func.__name__}")
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
