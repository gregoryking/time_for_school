import asyncio
from termdates import TermDates
from aiocron import crontab
import datetime

from light import Light

# TODO: Closed??? Exceptional, rsults in a closure operation?

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    td = TermDates('https://www.onslow.surrey.sch.uk/diary/ical/stUdcyHrjZwD/cat/4428/ics/')

    async def async_update_calendar():
        td.update_calendar() # won't actually be async, but what the hell, it'll be quick and infrequent
        await asyncio.sleep(0)

    async def run_time_for_school_lights():
        if td.is_greg_school_day(datetime.datetime.now().date()):
            await light.test_all()
        else:
            await asyncio.sleep(0)

    async def job(message='stuff', n=1):
        print("Asynchronous invocation (%s) of I'm working on:" % n, message)
        await asyncio.sleep(0)

    light = Light()
    loop.create_task(light.run())

    async def scheduler():
        while True:
            # await light.test_boogie()
            now = datetime.datetime.now()
            # Schedule calendar update at 3am on the first of every month
            if now.day == 1 and now.hour == 3 and now.minute == 0:
                await async_update_calendar()
            # Run time for school lights every school day morning at 07:15
            if now.hour == 7 and now.minute == 15:
                await run_time_for_school_lights()
            await asyncio.sleep(60)  # check every minute

    loop.create_task(scheduler())
    loop.run_forever()
