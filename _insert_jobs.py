import json
import sys
sys.path.insert(0, 'backend')
from app.database import save_job

with open('jobs_100.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)

for job in jobs:
    save_job(job)

print(f"Inserted {len(jobs)} jobs")
