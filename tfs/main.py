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
        if td.is_school_day(datetime.datetime.now().date()):
            await light.test_all()
        else:
            await asyncio.sleep(0)

    async def job(message='stuff', n=1):
        print("Asynchronous invocation (%s) of I'm working on:" % n, message)
        await asyncio.sleep(0)

    light = Light()
    loop.create_task(light.run())

    # Schedule updates to the calendar at 3am on first of every month
    crontab('0 3 1 * *', func=async_update_calendar, start=False)
    # crontab('40 12 * * *', func=async_update_calendar, start=True)
    # Run time for school lights every school day morning at 07:40
    crontab('40 7 * * *', func=run_time_for_school_lights, start=True)
    # crontab('30 12 * * *', func=run_time_for_school_lights, start=True)

    loop.run_forever()
