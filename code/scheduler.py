from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime


class Scheduler:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()

    def add_job(self, func, run_date: datetime, args=None, kwargs=None):
        self._scheduler.add_job(func, "date", args=args, kwargs=kwargs, run_date=run_date)


scheduler = Scheduler()