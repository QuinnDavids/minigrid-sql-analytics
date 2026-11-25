"""Create the four messy source files for the mini-grid pipeline.

Run from the project root:

    python scripts/generate_data.py

The data is synthetic. A fixed seed means every run writes identical files.
Each kind of mess is added on purpose, at the rate set in the constants below,
so the cleaning rules can be checked against it.
"""

from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

SEED = 42
N_CUSTOMERS = 300
START_DATE = date(2026, 3, 1)
N_DAYS = 120  # 2026-03-01 to 2026-06-28
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# ---- Reference lists ---------------------------------------------------------
FIRST_NAMES = [
    "Chinedu",
    "Ngozi",
    "Emeka",
    "Adaeze",
    "Tunde",
    "Funmilayo",
    "Ibrahim",
    "Aisha",
    "Tamuno",
    "Ibiere",
    "Obinna",
    "Chiamaka",
    "Segun",
    "Bisi",
    "Musa",
    "Hauwa",
    "Ebiere",
    "Preye",
    "Kelechi",
    "Amaka",
    "Uche",
    "Nneka",
    "Yusuf",
    "Zainab",
    "Boma",
    "Soye",
    "Ifeanyi",
    "Tari",
    "Ifeoma",
    "Dagogo",
]
LAST_NAMES = [
    "Okafor",
    "Eze",
    "Adeyemi",
    "Bello",
    "Briggs",
    "Amadi",
    "Nwosu",
    "Ogunleye",
    "Abubakar",
    "Wokoma",
    "Okeke",
    "Danjuma",
    "George",
    "Jumbo",
    "Ibe",
    "Obi",
    "Ekine",
    "Horsfall",
    "Ojo",
    "Sani",
]
COMMUNITIES = [
    "Rumuola",
    "Rumuokoro",
    "Elele",
    "Isiokpo",
    "Omagwa",
    "Abonnema",
    "Buguma",
    "Bori",
]
PHONE_PREFIXES = ["803", "806", "813", "703", "706", "810", "816", "902", "805", "807"]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# plan_id: (name, price per kWh in naira, typical daily kWh). Prices are illustrative.
PLANS = {
    "P01": ("Basic", 250, 1.5),
    "P02": ("Standard", 300, 3.0),
    "P03": ("Business", 350, 6.0),
    "P04": ("Productive Use", 280, 9.0),
}
PLAN_SHARES = [0.40, 0.30, 0.15, 0.15]
TOP_UP_AMOUNTS = [1000, 1500, 2000, 2500, 3000, 5000, 7500, 10000, 15000, 20000]
ORPHAN_IDS = [f"MG-{n:04d}" for n in range(901, 921)]

# ---- Mess rates --------------------------------------------------------------
MISSING_MARKERS = ["", "N/A", "none", "-", "null"]

RATE_CUSTOMER_ID_MESS = 0.10
RATE_COMMUNITY_LOWER = 0.10
RATE_COMMUNITY_UPPER = 0.10
RATE_HOUSEHOLD_TEXT = 0.06
RATE_HOUSEHOLD_IMPOSSIBLE = 0.03
RATE_CUSTOMER_DUPLICATES = 0.05
CUSTOMER_MISSING_RATES = {
    "phone": 0.03,
    "email": 0.05,
    "community": 0.03,
    "household_size": 0.04,
    "plan_id": 0.01,
    "signup_date": 0.02,
}

RATE_READING_PRESENT = 0.85
RATE_READING_ID_MESS = 0.05
RATE_ENERGY_ERROR = 0.01
RATE_ENERGY_BLANK = 0.01
RATE_ENERGY_NEGATIVE = 0.01
RATE_PEAK_DASH = 0.02
RATE_PEAK_OUT_OF_RANGE = 0.01
RATE_OUTAGE_WITH_H = 0.05
RATE_OUTAGE_OUT_OF_RANGE = 0.01
RATE_READING_EXACT_DUPLICATES = 0.03
RATE_READING_CONFLICTING_DUPLICATES = 0.02

RATE_EXTRA_SAME_DAY_PAYMENT = 0.06
RATE_ORPHAN_PAYMENTS = 0.02
RATE_PAYMENT_ID_MESS = 0.05
RATE_REVERSED_UNKNOWN = 0.02
RATE_REVERSED_TRUE = 0.03

# Date styles and how often each is used.
CUSTOMER_DATE_STYLES = {"iso": 0.5, "day_first_slash": 0.3, "named_month": 0.2}
EVENT_DATE_STYLES = {
    "iso": 0.40,
    "day_first_slash": 0.25,
    "named_month": 0.20,
    "year_first_slash": 0.15,
}


# ---- Small helpers -----------------------------------------------------------
def chance(rng: np.random.Generator, rate: float) -> bool:
    return rng.random() < rate


def pick(rng: np.random.Generator, items: list):
    return items[int(rng.integers(len(items)))]


def pick_weighted(rng: np.random.Generator, weights: dict[str, float]) -> str:
    names = list(weights)
    return names[int(rng.choice(len(names), p=list(weights.values())))]


def format_date(rng: np.random.Generator, day: date, styles: dict[str, float]) -> str:
    style = pick_weighted(rng, styles)
    if style == "iso":
        return day.strftime("%Y-%m-%d")
    if style == "day_first_slash":
        return day.strftime("%d/%m/%Y")
    if style == "year_first_slash":
        return day.strftime("%Y/%m/%d")
    return f"{day.day} {MONTH_ABBR[day.month - 1]} {day.year}"


def messy_id(rng: np.random.Generator, customer_id: str, rate: float) -> str:
    if not chance(rng, rate):
        return customer_id
    return pick(rng, [f" {customer_id.lower()} ", f" {customer_id} ", customer_id.lower()])


def format_naira(rng: np.random.Generator, amount: int) -> str:
    style = rng.random()
    if style < 0.25:
        return f"₦{amount:,}"
    if style < 0.45:
        return f"N{amount:,}"
    if style < 0.65:
        return f"NGN {amount}"
    return f"{amount:.2f}"


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    # utf-8-sig adds a marker so Excel shows the naira sign correctly.
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def shuffled(rng: np.random.Generator, rows: list[dict]) -> list[dict]:
    return [rows[i] for i in rng.permutation(len(rows))]


# ---- customers.csv -----------------------------------------------------------
CUSTOMER_COLUMNS = [
    "customer_id",
    "full_name",
    "phone",
    "email",
    "community",
    "household_size",
    "plan_id",
    "signup_date",
]


def make_true_customers(rng: np.random.Generator) -> list[dict]:
    """The real, clean facts about each customer. Used to build the other files."""
    customers = []
    for number in range(1, N_CUSTOMERS + 1):
        first, last = pick(rng, FIRST_NAMES), pick(rng, LAST_NAMES)
        customers.append(
            {
                "customer_id": f"MG-{number:04d}",
                "full_name": f"{first} {last}",
                "phone": "0" + pick(rng, PHONE_PREFIXES) + f"{int(rng.integers(0, 10**7)):07d}",
                "email": f"{first}.{last}{number}@example.com".lower(),
                "community": pick(rng, COMMUNITIES),
                "household_size": int(rng.integers(1, 11)),
                "plan_id": pick_weighted(rng, dict(zip(PLANS, PLAN_SHARES, strict=True))),
                "signup_date": START_DATE - timedelta(days=int(rng.integers(10, 300))),
            }
        )
    return customers


def mess_up_customer(rng: np.random.Generator, customer: dict) -> dict:
    community = customer["community"]
    roll = rng.random()
    if roll < RATE_COMMUNITY_LOWER:
        community = community.lower() + " "
    elif roll < RATE_COMMUNITY_LOWER + RATE_COMMUNITY_UPPER:
        community = community.upper()

    household = str(customer["household_size"])
    roll = rng.random()
    if roll < RATE_HOUSEHOLD_TEXT:
        household = f"{household} people"
    elif roll < RATE_HOUSEHOLD_TEXT + RATE_HOUSEHOLD_IMPOSSIBLE:
        household = pick(rng, ["-1", "45"])

    row = {
        "customer_id": messy_id(rng, customer["customer_id"], RATE_CUSTOMER_ID_MESS),
        "full_name": customer["full_name"],
        "phone": customer["phone"],
        "email": customer["email"],
        "community": community,
        "household_size": household,
        "plan_id": customer["plan_id"],
        "signup_date": format_date(rng, customer["signup_date"], CUSTOMER_DATE_STYLES),
    }
    for column, rate in CUSTOMER_MISSING_RATES.items():
        if chance(rng, rate):
            row[column] = pick(rng, MISSING_MARKERS)
    return row


def make_customers_file(rng: np.random.Generator, customers: list[dict]) -> list[dict]:
    rows = [mess_up_customer(rng, customer) for customer in customers]
    n_duplicates = round(N_CUSTOMERS * RATE_CUSTOMER_DUPLICATES)
    for index in rng.choice(N_CUSTOMERS, size=n_duplicates, replace=False):
        # A second team re-keyed the same customer and left the email out.
        copy = mess_up_customer(rng, customers[int(index)])
        copy["email"] = ""
        rows.append(copy)
    return shuffled(rng, rows)


# ---- tariff_plans.csv --------------------------------------------------------
TARIFF_COLUMNS = ["plan_id", "plan_name", "price_per_kwh"]


def make_tariff_file(rng: np.random.Generator) -> list[dict]:
    rows = []
    for plan_id, (name, price, _) in PLANS.items():
        # The correct spelling twice, then two badly typed variants.
        spellings = [name, name, name.lower() + " ", name.upper()]
        prices = [f"₦{price}", f"{price}", f"{price}.00 NGN", f"{price}"]
        for spelling, written_price in zip(spellings, prices, strict=True):
            rows.append({"plan_id": plan_id, "plan_name": spelling, "price_per_kwh": written_price})
    return shuffled(rng, rows)


# ---- meter_readings.csv ------------------------------------------------------
READING_COLUMNS = ["customer_id", "reading_date", "energy_used", "peak_load_kw", "outage_hours"]


def format_energy(rng: np.random.Generator, kwh: float) -> str:
    roll = rng.random()
    if roll < RATE_ENERGY_ERROR:
        return "error"
    roll -= RATE_ENERGY_ERROR
    if roll < RATE_ENERGY_BLANK:
        return ""
    roll -= RATE_ENERGY_BLANK
    if roll < RATE_ENERGY_NEGATIVE:
        return f"-{kwh:.1f} kWh"
    style = rng.random()
    if style < 0.40:
        return f"{kwh:.1f} kWh"
    if style < 0.55:
        return f"{kwh * 1000:.0f} Wh"
    if style < 0.70:
        return f"{kwh:.1f}kwh"
    return f"{kwh:.2f}"


def format_peak(rng: np.random.Generator, kw: float) -> str:
    roll = rng.random()
    if roll < RATE_PEAK_DASH:
        return "-"
    if roll < RATE_PEAK_DASH + RATE_PEAK_OUT_OF_RANGE:
        return "99"
    if rng.random() < 0.30:
        return f"{kw:.1f} kW"
    return f"{kw:.2f}"


def format_outage(rng: np.random.Generator, hours: float) -> str:
    roll = rng.random()
    if roll < RATE_OUTAGE_OUT_OF_RANGE:
        return "30"
    if roll < RATE_OUTAGE_OUT_OF_RANGE + RATE_OUTAGE_WITH_H:
        return f"{hours:g}h"
    return f"{hours:g}"


def typical_daily_kwh(customer: dict) -> float:
    """A customer's usual daily use: set by their plan, a little more for bigger households."""
    return PLANS[customer["plan_id"]][2] * (0.7 + 0.06 * customer["household_size"])


def make_readings_file(rng: np.random.Generator, customers: list[dict]) -> list[dict]:
    rows, keys = [], []
    for customer in customers:
        for offset in range(N_DAYS):
            if not chance(rng, RATE_READING_PRESENT):
                continue  # no reading that day: a gap
            day = START_DATE + timedelta(days=offset)
            kwh = typical_daily_kwh(customer) * float(rng.lognormal(0, 0.3))
            peak_kw = min(kwh / float(rng.uniform(3, 6)), 18.0)
            outage = 0.0 if chance(rng, 0.7) else round(float(rng.uniform(0.5, 6)), 1)
            rows.append(
                {
                    "customer_id": messy_id(rng, customer["customer_id"], RATE_READING_ID_MESS),
                    "reading_date": format_date(rng, day, EVENT_DATE_STYLES),
                    "energy_used": format_energy(rng, kwh),
                    "peak_load_kw": format_peak(rng, peak_kw),
                    "outage_hours": format_outage(rng, outage),
                }
            )
            keys.append((customer["customer_id"], day))

    n_readings = len(rows)
    n_exact = round(n_readings * RATE_READING_EXACT_DUPLICATES)
    for index in rng.choice(n_readings, size=n_exact, replace=False):
        rows.append(dict(rows[int(index)]))  # identical copy

    n_conflicting = round(n_readings * RATE_READING_CONFLICTING_DUPLICATES)
    for index in rng.choice(n_readings, size=n_conflicting, replace=False):
        customer_id, day = keys[int(index)]
        rows.append(
            {
                # Same customer and day, typed differently, with the values left out.
                "customer_id": messy_id(rng, customer_id, 0.5),
                "reading_date": format_date(rng, day, EVENT_DATE_STYLES),
                "energy_used": pick(rng, MISSING_MARKERS),
                "peak_load_kw": pick(rng, MISSING_MARKERS),
                "outage_hours": pick(rng, MISSING_MARKERS),
            }
        )
    return shuffled(rng, rows)


# ---- payments.csv ------------------------------------------------------------
PAYMENT_COLUMNS = ["payment_id", "customer_id", "payment_date", "amount", "channel", "is_reversed"]
CHANNEL_SPELLINGS = {
    "USSD": ["USSD", "ussd", " Ussd"],
    "Bank Transfer": ["Bank Transfer", "bank transfer ", "BANK TRANSFER"],
    "POS": ["POS", "pos"],
    "Card": ["Card", "card"],
}
CHANNEL_SHARES = {"USSD": 0.35, "Bank Transfer": 0.30, "POS": 0.20, "Card": 0.15}


def format_reversed(rng: np.random.Generator) -> str:
    roll = rng.random()
    if roll < RATE_REVERSED_UNKNOWN:
        return pick(rng, ["", "maybe"])
    if roll < RATE_REVERSED_UNKNOWN + RATE_REVERSED_TRUE:
        return pick(rng, ["Y", "yes", "1", "TRUE"])
    return pick(rng, ["N", "0", "false", "no"])


def round_to_500(amount: float) -> int:
    return max(500, int(round(amount / 500)) * 500)


def make_payments_file(rng: np.random.Generator, customers: list[dict]) -> list[dict]:
    events = []  # (customer_id, day offset, amount in naira)
    for customer in customers:
        price = PLANS[customer["plan_id"]][1]
        # lognormal(0, 0.3) used for daily readings averages about 1.046.
        daily_cost = typical_daily_kwh(customer) * 1.046 * price
        offset = int(rng.integers(0, 7))
        while offset < N_DAYS:
            # Each top-up roughly covers the days until the next one, give or take.
            days_covered = int(rng.integers(4, 11))
            top_up = round_to_500(daily_cost * days_covered * float(rng.uniform(0.85, 1.10)))
            events.append((customer["customer_id"], offset, top_up))
            if chance(rng, RATE_EXTRA_SAME_DAY_PAYMENT):
                small_top_up = pick(rng, [500, 1000, 1500])
                events.append((customer["customer_id"], offset, small_top_up))  # second that day
            offset += days_covered

    n_orphans = round(len(events) * RATE_ORPHAN_PAYMENTS)
    for _ in range(n_orphans):
        events.append(
            (pick(rng, ORPHAN_IDS), int(rng.integers(0, N_DAYS)), pick(rng, TOP_UP_AMOUNTS))
        )

    events.sort(key=lambda event: (event[1], event[0]))
    rows = []
    for number, (customer_id, offset, amount) in enumerate(events, start=1):
        channel = pick_weighted(rng, CHANNEL_SHARES)
        rows.append(
            {
                "payment_id": f"PAY-{number:06d}",
                "customer_id": messy_id(rng, customer_id, RATE_PAYMENT_ID_MESS),
                "payment_date": format_date(
                    rng, START_DATE + timedelta(days=offset), EVENT_DATE_STYLES
                ),
                "amount": format_naira(rng, amount),
                "channel": pick(rng, CHANNEL_SPELLINGS[channel]),
                "is_reversed": format_reversed(rng),
            }
        )
    return shuffled(rng, rows)


# ---- Main --------------------------------------------------------------------
def generate(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, int]:
    """Write the four messy CSV files into out_dir and return the row count of each."""
    rng = np.random.default_rng(SEED)
    out_dir.mkdir(parents=True, exist_ok=True)

    customers = make_true_customers(rng)
    files = {
        "customers.csv": (CUSTOMER_COLUMNS, make_customers_file(rng, customers)),
        "tariff_plans.csv": (TARIFF_COLUMNS, make_tariff_file(rng)),
        "meter_readings.csv": (READING_COLUMNS, make_readings_file(rng, customers)),
        "payments.csv": (PAYMENT_COLUMNS, make_payments_file(rng, customers)),
    }
    counts = {}
    for name, (columns, rows) in files.items():
        write_csv(out_dir / name, columns, rows)
        counts[name] = len(rows)
    return counts


def print_sample(path: Path, n_rows: int = 6) -> None:
    with path.open(encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file):
            if line_number > n_rows:
                break
            print("   ", line.rstrip())


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # so the naira sign prints on Windows
    counts = generate(DEFAULT_OUT_DIR)
    for name, n_rows in counts.items():
        print(f"\n{name}: {n_rows:,} rows -> {DEFAULT_OUT_DIR / name}")
        print_sample(DEFAULT_OUT_DIR / name)


if __name__ == "__main__":
    main()
