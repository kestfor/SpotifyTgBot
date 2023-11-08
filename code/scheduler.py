from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime


class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._jobs = {}

    def add_job(self, func, run_date: datetime, uri):
        job = self.scheduler.add_job(func, "date", args=[uri], run_date=run_date)
        self._jobs[uri] = job

    def remove_job(self, uri):
        self.scheduler.remove_job(self._jobs[uri].id)
        self._jobs.pop(uri)
