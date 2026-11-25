"""Checks that each cleaned view meets its rules, and that every analysis returns rows.

The whole project is built once, from freshly generated data, into a temporary folder.
"""

import importlib.util
from pathlib import Path

import duckdb
import pytest

import run as runner

ROOT = Path(__file__).resolve().parents[1]
MISSING_TOKENS = ("", "n/a", "na", "none", "-", "null", "nan")


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_data", ROOT / "scripts" / "generate_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("sql")
    load_generator().generate(base / "raw")
    results = runner.run(base / "raw", base / "minigrid.duckdb", base / "results")
    connection = duckdb.connect(str(base / "minigrid.duckdb"), read_only=True)
    yield connection, results, base
    connection.close()


def scalar(connection, sql: str):
    return connection.execute(sql).fetchone()[0]


# ---- clean_customers ---------------------------------------------------------
def test_customer_ids_are_unique_and_never_null(built):
    db, _, _ = built
    assert scalar(db, "SELECT COUNT(*) FROM clean_customers WHERE customer_id IS NULL") == 0
    assert scalar(db, "SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM clean_customers") == 0
    assert scalar(db, "SELECT COUNT(*) FROM clean_customers") == 300


@pytest.mark.parametrize(
    "column", ["customer_id", "full_name", "phone", "email", "community", "plan_id"]
)
def test_no_missing_tokens_left_in_customers(built, column):
    db, _, _ = built
    tokens = ", ".join(f"'{token}'" for token in MISSING_TOKENS)
    assert scalar(
        db, f"SELECT COUNT(*) FROM clean_customers WHERE LOWER(TRIM({column})) IN ({tokens})"
    ) == 0


def test_community_is_tidy(built):
    db, _, _ = built
    communities = {row[0] for row in db.execute("SELECT DISTINCT community FROM clean_customers").fetchall()}
    assert all(name == name.strip() and name[0].isupper() and name[1:].islower() for name in communities)


def test_household_size_filled_and_in_range(built):
    db, _, _ = built
    assert scalar(db, "SELECT COUNT(*) FROM clean_customers WHERE household_size IS NULL") == 0
    assert scalar(db, "SELECT COUNT(*) FROM clean_customers WHERE household_size NOT BETWEEN 1 AND 30") == 0
    assert scalar(db, "SELECT COUNT(*) FROM clean_customers WHERE household_size_was_filled") > 0


# ---- clean_tariff_plans ------------------------------------------------------
def test_one_row_per_plan_with_canonical_names(built):
    db, _, _ = built
    rows = db.execute("SELECT plan_id, plan_name, price_per_kwh FROM clean_tariff_plans ORDER BY plan_id").fetchall()
    assert rows == [
        ("P01", "Basic", 250.0),
        ("P02", "Standard", 300.0),
        ("P03", "Business", 350.0),
        ("P04", "Productive Use", 280.0),
    ]


def test_every_price_spelling_of_a_plan_agrees(built):
    db, _, _ = built
    assert scalar(
        db,
        "SELECT MAX(n) FROM (SELECT COUNT(DISTINCT parse_naira(price_per_kwh)) AS n "
        "FROM raw_tariff_plans GROUP BY clean_id(plan_id))",
    ) == 1


# ---- clean_meter_readings ----------------------------------------------------
def test_energy_is_never_negative(built):
    db, _, _ = built
    assert scalar(db, "SELECT COUNT(*) FROM clean_meter_readings WHERE energy_kwh < 0") == 0


def test_outage_hours_within_0_to_24(built):
    db, _, _ = built
    assert scalar(db, "SELECT COUNT(*) FROM clean_meter_readings WHERE outage_hours NOT BETWEEN 0 AND 24") == 0


def test_peak_load_within_0_to_20(built):
    db, _, _ = built
    assert scalar(db, "SELECT COUNT(*) FROM clean_meter_readings WHERE peak_load_kw NOT BETWEEN 0 AND 20") == 0


def test_one_reading_per_customer_per_day(built):
    db, _, _ = built
    assert scalar(
        db,
        "SELECT COUNT(*) FROM (SELECT customer_id, reading_date FROM clean_meter_readings "
        "GROUP BY 1, 2 HAVING COUNT(*) > 1)",
    ) == 0


def test_wh_readings_are_converted(built):
    db, _, _ = built
    # No real daily reading is anywhere near 1,000 kWh; an unconverted Wh value would be.
    assert scalar(db, "SELECT MAX(energy_kwh) FROM clean_meter_readings") < 100


# ---- clean_payments ----------------------------------------------------------
def test_amounts_are_numeric_and_positive(built):
    db, _, _ = built
    assert scalar(db, "SELECT COUNT(*) FROM clean_payments WHERE amount_ngn IS NULL OR amount_ngn <= 0") == 0
    data_type = scalar(
        db,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'clean_payments' AND column_name = 'amount_ngn'",
    )
    assert data_type == "DOUBLE"


def test_reversed_flag_is_true_false_or_null_only(built):
    db, _, _ = built
    values = {row[0] for row in db.execute("SELECT DISTINCT is_reversed FROM clean_payments").fetchall()}
    assert values == {True, False, None}


def test_channels_are_official_names(built):
    db, _, _ = built
    channels = {row[0] for row in db.execute("SELECT DISTINCT channel FROM clean_payments").fetchall()}
    assert channels == {"USSD", "Bank Transfer", "POS", "Card"}


# ---- customer_daily ----------------------------------------------------------
def test_customer_daily_key_is_unique(built):
    db, _, _ = built
    assert scalar(
        db,
        "SELECT COUNT(*) FROM (SELECT customer_id, date FROM customer_daily "
        "GROUP BY 1, 2 HAVING COUNT(*) > 1)",
    ) == 0


def test_customer_daily_has_no_unknown_customers(built):
    db, _, _ = built
    assert scalar(
        db,
        "SELECT COUNT(*) FROM customer_daily d "
        "LEFT JOIN clean_customers c ON c.customer_id = d.customer_id WHERE c.customer_id IS NULL",
    ) == 0


def test_payment_status_matches_count(built):
    db, _, _ = built
    assert scalar(
        db,
        "SELECT COUNT(*) FROM customer_daily WHERE "
        "(payment_count > 0 AND payment_status <> 'Paid') OR "
        "(payment_count = 0 AND payment_status <> 'No payment')",
    ) == 0


def test_missing_plans_are_filled_from_tariff_table(built):
    db, _, _ = built
    assert scalar(db, "SELECT COUNT(*) FROM customer_daily WHERE plan_name IS NULL") == 0
    assert scalar(db, "SELECT COUNT(*) FROM customer_daily WHERE plan_was_defaulted") > 0


# ---- analysis queries --------------------------------------------------------
@pytest.mark.parametrize("name", list(runner.QUESTIONS))
def test_each_analysis_returns_rows(built, name):
    _, results, base = built
    assert len(results[name]) >= 1
    assert (base / "results" / f"{name}.csv").exists()


def test_results_markdown_is_written(built):
    _, _, base = built
    text = (base / "results" / "RESULTS.md").read_text(encoding="utf-8")
    for name in runner.QUESTIONS:
        assert f"## {name}" in text
