import pandas as pd, numpy as np
from pathlib import Path
import sys

# If a seed is provided as an argument, use it. Otherwise use random.
if len(sys.argv) > 1:
    seed = int(sys.argv[1])
    rng = np.random.default_rng(seed)
    print(f"🔀 Using seed {seed}")
else:
    rng = np.random.default_rng()
    print("🔀 Using random seed")


root = Path(__file__).resolve().parents[1]
raw = root / "data" / "raw"
raw.mkdir(parents=True, exist_ok=True)

# patients
n_patients = 120
patients = pd.DataFrame(
    {
        "patient_id": np.arange(1, n_patients + 1),
        "first_name": [f"Pat{i}" for i in range(1, n_patients + 1)],
        "last_name": [f"Smith{i}" for i in range(1, n_patients + 1)],
        "phone": [
            f"+49-170-{rng.integers(1000000,9999999)}" for _ in range(n_patients)
        ],
        "consent_form_received": rng.integers(0, 2, size=n_patients),
        "created_at": pd.Timestamp.today(tz="Europe/Berlin")
        - pd.to_timedelta(rng.integers(1, 200, size=n_patients), unit="D"),
    }
)
patients.to_csv(raw / "patients.csv", index=False)

# physios
physio_names = ["Alex J", "Marta K", "Lukas T", "Sara P"]
physios = pd.DataFrame(
    {"physio_id": np.arange(1, len(physio_names) + 1), "full_name": physio_names}
)
physios.to_csv(raw / "physios.csv", index=False)

# appointments over last 21 days and today
days = pd.date_range(
    end=pd.Timestamp.today(tz="Europe/Berlin").normalize(),
    periods=22,
    tz="Europe/Berlin",
)
rows = []
aid = 1
for d in days:
    n = rng.integers(18, 32)  # daily load
    for _ in range(n):
        pid = int(rng.integers(1, n_patients + 1))
        ph = int(rng.integers(1, len(physio_names) + 1))
        start_hour = int(rng.choice([8, 9, 10, 11, 12, 13, 14, 15, 16, 17]))
        start = pd.Timestamp(
            year=d.year,
            month=d.month,
            day=d.day,
            hour=start_hour,
            minute=0,
            tz="Europe/Berlin",
        )
        end = start + pd.Timedelta(minutes=int(rng.choice([30, 45, 60])))
        booked_at = start - pd.Timedelta(days=int(rng.integers(1, 30)))
        status = rng.choice(["completed", "canceled", "no_show"], p=[0.75, 0.15, 0.10])
        price = float(rng.choice([45, 60, 75, 90]))
        rows.append(
            [
                aid,
                pid,
                ph,
                start.isoformat(),
                end.isoformat(),
                booked_at.isoformat(),
                status,
                price,
            ]
        )
        aid += 1

appointments = pd.DataFrame(
    rows,
    columns=[
        "appointment_id",
        "patient_id",
        "physio_id",
        "appt_start",
        "appt_end",
        "booked_at",
        "status",
        "price_estimate",
    ],
)
appointments.to_csv(raw / "appointments.csv", index=False)

# payments for completed only
completed = appointments[appointments["status"] == "completed"].copy()
payments = completed[["appointment_id", "appt_end"]].copy()
payments["payment_id"] = np.arange(1, len(payments) + 1)
payments["amount"] = payments["appointment_id"].map(
    lambda _: float(rng.choice([45, 60, 75, 90]))
)
payments["paid_at"] = payments["appt_end"]
payments["method"] = rng.choice(
    ["card", "cash", "invoice"], size=len(payments), p=[0.6, 0.3, 0.1]
)
payments = payments[["payment_id", "appointment_id", "amount", "paid_at", "method"]]
payments.to_csv(raw / "payments.csv", index=False)

print("Mock CSVs written to data/raw/")
