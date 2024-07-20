import datetime
import requests
import icalendar
import re
import portion as P
import logging
import sys

# TODO: Put general logger config in dedicated file

log = logging.getLogger('TermDates')
log.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

UPDATE_AFTER_DAYS = 30

def find_matches(d, item):
    for k in d:
        if re.match(k, item, re.IGNORECASE):
            return d[k]


class TermDates:
    def __init__(self, ics_uri):
        self.__ics_uri = ics_uri
        self.__ics_cache_path = 'cache.ics'
        self.__ics = None
        self.__initialise_calendar()
        self.__ranges = self.__get_ranges()

    def __initialise_calendar(self):
        try:
            self.__load_calendar_from_cache()
        except FileNotFoundError as e:
            self.__download_calendar()

    def __download_calendar(self):
        try:
            ics_content = requests.get(self.__ics_uri, allow_redirects=True).content
        except requests.exceptions.RequestException as e:
            log.info("Could not download calendar")
        else:
            log.info("Downloaded calendar")
            self.__ics = ics_content
            self.__cache_calendar()

    def __cache_calendar(self):
        try:
            f = open(self.__ics_cache_path, 'wb')
        except OSError:
            log.error('Could not open cache file for writing')
        else:
            log.info("Caching calendar")
            f.write(self.__ics)

    def __load_calendar_from_cache(self):
        try:
            f = open(self.__ics_cache_path, 'r')
        except OSError as e:
            log.error('Could not open cache file for reading')
            raise e
        else:
            log.info("Loading calendar from cache")
            self.__ics = f.read()

    def update_calendar(self):
        self.__download_calendar()
        self.__get_ranges()


    def __get_ranges(self):
        log.info("Getting ranges from calendar")
        regexes = {'End of \w+ Term': lambda x, y: [P.closed(-P.inf, x), 'termEnd'],
                   'Start of \w+ Term': lambda x, y: [P.closed(x, P.inf), 'termStart'],
                   'INSET Day': lambda x, y: [P.singleton(x), 'subtract'],  # to subtract
                   '(\w+ )?Bank Holiday': lambda x, y: [P.singleton(x), 'subtract'],  # to intersct
                   '(\w+ )?Half Term': lambda x, y: [P.closed(x, y), 'subtract']}  # to intersct
        calendar = icalendar.Calendar.from_ical(self.__ics)

        term_end = P.empty()
        term_start = P.empty()
        term_time_off = P.empty()
        total_range = P.empty()

        for e in calendar.walk('vevent'):
            match = find_matches(regexes, e['SUMMARY'])
            if match is not None:
                ds = e['DTSTART'].dt
                de = e['DTEND'].dt
                if isinstance(ds, datetime.datetime):
                    ds = ds.date()
                if isinstance(de, datetime.datetime):
                    de = de.date()
                range_val, range_type = match(ds, de)
                if range_type == 'termEnd':
                    term_end = range_val
                elif range_type == 'subtract':
                    term_time_off |= range_val
                elif range_type == 'termStart' and term_end is not P.empty():
                    term_start = range_val
                    term = term_start.intersection(term_end)
                    term_valid_days = term - term_time_off
                    total_range |= term_valid_days
                    term_end = P.empty()
                    term_start = P.empty()
        return total_range

    def is_school_day(self, date):
        return date in self.__ranges and date.weekday() < 5
    
    def is_greg_school_day(self, date):
        return date in self.__ranges and date.weekday() < 5 and date.isocalendar().week % 2 == 0