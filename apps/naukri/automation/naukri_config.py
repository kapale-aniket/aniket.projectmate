from pathlib import Path

_HERE = Path(__file__).resolve().parent
OUTPUT_DIR = _HERE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STORAGE_STATE_PATH = str(_HERE / "storage_state.json")

HISTORY_URL = "https://www.naukri.com/myapply/historypage"
RECOMMENDED_URL = "https://www.naukri.com/mnjuser/recommendedjobs"

# Filter recommended jobs that contain this keyword (case-insensitive)
JOB_KEYWORD = "python"

# How many Python jobs to select and multi-apply in one batch
MULTI_APPLY_BATCH_SIZE = 5

# Only keep application-history rows for "today"
HISTORY_STATUS_FILTER = "connected by email"

MIN_DELAY = 1.0
MAX_DELAY = 2.0

HISTORY_CSV = str(OUTPUT_DIR / "today_email_applications.csv")
HISTORY_XLSX = str(OUTPUT_DIR / "today_email_applications.xlsx")
RECOMMENDED_CSV = str(OUTPUT_DIR / "python_recommended_jobs.csv")
RECOMMENDED_XLSX = str(OUTPUT_DIR / "python_recommended_jobs.xlsx")
APPLIED_CSV = str(OUTPUT_DIR / "multi_applied_jobs.csv")
