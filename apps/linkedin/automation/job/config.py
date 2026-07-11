import os

JOB_KEYWORDS = ['Python Developer Fresher', 'Django Developer Fresher']
LOCATIONS = ['Pune', 'Bangalore']
MAX_PAGES = 40
MAX_JOBS = int(os.getenv("MAX_JOBS", "0"))
MAX_JOB_AGE_HOURS = 2
SEARCH_MIN_DELAY = 1.0
SEARCH_MAX_DELAY = 2.0
RESULTS_PER_PAGE = 25
