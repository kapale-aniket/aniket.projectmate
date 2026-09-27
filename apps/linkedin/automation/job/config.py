import os

JOB_KEYWORDS = ['Djanago developer fresher', 'python developer fresher', 'java developer', 'data analytics fresher']
LOCATIONS = ['bangalore', 'pune', 'navi mumbai', 'hyderabad']
MAX_PAGES = 40
MAX_JOBS = int(os.getenv("MAX_JOBS", "0"))
MAX_JOB_AGE_HOURS = 24
SEARCH_MIN_DELAY = 1.0
SEARCH_MAX_DELAY = 2.0
SHEET_TITLE = 'aniket.projectmate daily jobs'
WHATSAPP_GROUP_URL = 'https://chat.whatsapp.com/GV7XEmVREg9KrB1sr5dZwL'
WHATSAPP_GROUP_NAME = 'Be Placement Ready'
INSTAGRAM_URL = 'https://www.instagram.com/aniket.projectmate?igsh=MWtkbWs3bGE1N2Jtag=='
INSTAGRAM_HANDLE = 'aniket.projectmate'
SKIP_SEARCHES = []
SKIP_PREVIOUS_JOBS = False
SCRAPE_MODE = 'job'
PERFECT_MATCH_SKILLS = []
PERFECT_MATCH_EXPERIENCE = ''
PERFECT_MATCH_MIN_SKILLS = 1
JOB_SEARCH_DISTANCE_KM = 100
JOB_SEARCH_SORT_BY = 'R'
RESULTS_PER_PAGE = 25
