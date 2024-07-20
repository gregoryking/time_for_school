import asyncio
from contextlib import AsyncExitStack
from asyncio_mqtt import Client, MqttError
import random
from colour import Color
import logging
import sys

log = logging.getLogger('Light')
log.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

RUN_TIME_S = 75 * 60 # 75 mins

# Start at 07:15
# End at 08:30
# 75 mins total
# 30 mins Green
# 40 mins transition
# 2 mins red
# 3 mins rainbow boogie

sequence = [
    {
        'type': 'solid',
        'type_params':
            {
                'colour': '#00ff00'
            },
        'duration': 30/75
    },
    {
        'type': 'gradient',
        'type_params':
            {
                'from_colour': '#00ff00',
                'to_colour': '#e24c00',
                'freq': 0.01
            },
        'duration': (40/75)/2
    },
    {
        'type': 'gradient',
        'type_params':
            {
                'from_colour': '#e24c00',
                'to_colour': '#ff0000',
                'freq': 0.01
            },
        'duration': (40/75)/2
    },
    {
        'type': 'solid',
        'type_params':
            {
                'colour': '#ff0000'
            },
        'duration': 2/75
    },
    {
        'type': 'rainbow_boogie',
        'type_params':
            {
                'freq': 0.1
            },

        'duration': 3/75
    },
]

class Light(object):

    def __init__(self):
        self.__tasks = set()
        self.__client = Client("homebridge.local")

    async def create(self):
        async with AsyncExitStack() as stack:
            # Keep track of the asyncio tasks that we create, so that
            # we can cancel them on exit
            stack.push_async_callback(self.__cancel_tasks, self.__tasks)

            # Connect to the MQTT broker

            client = self.__client
            await stack.enter_async_context(client)
            # You can create any number of topic filters
            topic_filters = (
                "stat/kitchen-mood-light/POWER",
            )
            for topic_filter in topic_filters:
                # Log all messages that matches the filter
                manager = client.filtered_messages(topic_filter)
                messages = await stack.enter_async_context(manager)
                template = f'[topic_filter="{topic_filter}"] {{}}'
                task = asyncio.create_task(self.__log_messages(messages, template))
                self.__tasks.add(task)

            # Messages that doesn't match a filter will get logged here
            messages = await stack.enter_async_context(client.unfiltered_messages())
            task = asyncio.create_task(self.__log_messages(messages, "[unfiltered] {}"))
            self.__tasks.add(task)

            # Subscribe to topic(s)
            # 🤔 Note that we subscribe *after* starting the message
            # loggers. Otherwise, we may miss retained messages.
            await client.subscribe("stat/kitchen-mood-light/POWER")
            log.info("Subscribed to stat/kitchen-mood-light/POWER")

            # Publish a random value to each of these topics
            topics = (
                "cmnd/kitchen-mood-light/COLOR",
            )

            await asyncio.gather(*self.__tasks)

    async def run(self):
        reconnect_interval = 3  # [seconds]
        while True:
            try:
                await self.create()
            except MqttError as error:
                log.error(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
            finally:
                await asyncio.sleep(reconnect_interval)

    async def __set_colour(self, color):
        colour = Color(color).get_hex_l() + '00' # Set white channel to off for colourful stuff
        await self.__client.publish("cmnd/kitchen-mood-light/COLOR", colour)

    async def __set_white(self):
        colour = '000000ff'
        await self.__client.publish("cmnd/kitchen-mood-light/COLOR", colour)

    async def __solid_colour(self, type_params, duration):
        print("Solid")
        duration_s = duration * RUN_TIME_S
        await self.__set_colour(type_params['colour'])
        await asyncio.sleep(duration_s)

    async def __gradient_colour(self, type_params, duration):
        print("Gradient")
        from_colour = Color(type_params['from_colour'])
        to_colour = Color(type_params['to_colour'])
        freq = max(type_params['freq'],0.1)
        duration_s = duration * RUN_TIME_S
        gradient_steps = int(duration_s / freq)
        gradient = list(from_colour.range_to(to_colour, 2 + gradient_steps))
        time_between_steps = duration_s / (gradient_steps + 1)
        for step in gradient:
            await self.__set_colour(step)
            await asyncio.sleep(time_between_steps)

    def __random_colour(self):
        r = lambda: random.randint(0, 255)
        return '#%02X%02X%02X' % (r(), r(), r())

    async def __rainbow_boogie(self, type_params, duration):
        print("Rainbow")
        freq = max(type_params['freq'],0.1)
        duration_s = duration * RUN_TIME_S
        num_steps = int(duration_s / freq)
        for step in range(num_steps):
            await self.__set_colour(self.__random_colour())
            await asyncio.sleep(freq)
        await self.__set_white()

    def add_test_all_task(self):
        task = asyncio.create_task(self.test_all())
        self.__tasks.add(task)

    async def test_all(self):
        seq0 = sequence[0]
        seq1 = sequence[1]
        seq2 = sequence[2]
        seq3 = sequence[3]
        seq4 = sequence[4]
        await self.__solid_colour(seq0['type_params'], seq0['duration'])
        await self.__gradient_colour(seq1['type_params'], seq1['duration'])
        await self.__gradient_colour(seq2['type_params'], seq2['duration'])
        await self.__solid_colour(seq3['type_params'], seq3['duration'])
        await self.__rainbow_boogie(seq4['type_params'], seq4['duration'])
        await self.__client.publish("cmnd/kitchen-mood-light/POWER", "OFF", qos=1)

    async def __post_to_topics(self, topics):
        while True:
            for topic in topics:
                r = lambda: random.randint(0, 255)
                random_hex = '#%02X%02X%02X00' % (r(), r(), r())
                print(f'[topic="{topic}"] Publishing message={random_hex}')
                await self.__client.publish(topic, random_hex, qos=1)
                await asyncio.sleep(3)

    async def __log_messages(self, messages, template):
        async for message in messages:
            # 🤔 Note that we assume that the message paylod is an
            # UTF8-encoded string (hence the `bytes.decode` call).
            print(template.format(message.payload.decode()))

    async def __cancel_tasks(self, tasks):
        for task in tasks:
            if task.done():
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def subscribe(self, topic):
        await self.__client.subscribe(topic)