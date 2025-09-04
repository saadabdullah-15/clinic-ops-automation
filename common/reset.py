import os
from pathlib import Path
import subprocess
import sys
import random

root = Path(__file__).resolve().parents[1]
db_file = root / "clinic.db"

# 1. Delete DB if exists
if db_file.exists():
    db_file.unlink()
    print("✅ Deleted old clinic.db")

# 2. Regenerate mock CSVs with a random seed
seed = random.randint(1, 1000000)
print(f"➡️ Generating mock data with seed {seed}...")
subprocess.run([sys.executable, "common/generate_mock_data.py", str(seed)], check=True)

# 3. Reload DB
print("➡️ Loading data into DB...")
subprocess.run([sys.executable, "-m", "01_kpi_dashboard.etl.load"], check=True)

# 4. Launch Streamlit dashboard
print("🚀 Launching Streamlit...")
subprocess.run([sys.executable, "-m", "streamlit", "run", "01_kpi_dashboard/app.py"])
