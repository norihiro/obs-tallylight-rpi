#! /usr/bin/python3
'Tally light control using Raspberry PI GPIO'

import asyncio
import argparse
import datetime
import simpleobsws
try:
    from RPi import GPIO
except (RuntimeError, ModuleNotFoundError) as e:
    print(f'Failed to load rpi.gpio: {e}\nUsing dummy GPIO...')
    class GPIO:
        'Just print GPIO controls'
        # pylint: disable=C0116
        @staticmethod
        def setmode(mode):
            pass
        @staticmethod
        def output(gpio, active):
            print(f'GPIO.output({gpio}, {active})')
        @staticmethod
        def setup(*args):
            print(f'GPIO.setup({", ".join(args)})')
        BOARD = 'GPIO.BOARD'
        OUT = 'GPIO.OUT'


class Tally:
    'Tally light control class'

    def __init__(self, args):
        self.studio_mode = False
        self.ws = None
        self.args = args

        self.assigns = {}
        for gpio_source in args.assign:
            gpio, source = gpio_source.split('=', 1)
            self.assigns[source] = int(gpio)

        self.source_active_states = {}

        self.gpio_drives_prev = {}
        GPIO.setmode(GPIO.BOARD)
        for _, gpio in self.assigns.items():
            GPIO.setup(gpio, GPIO.OUT)
            GPIO.output(gpio, False)
            self.gpio_drives_prev[gpio] = False

    async def ws_connect(self, host, port, password):
        'Connect to obs-websocket server'
        param = simpleobsws.IdentificationParameters()
        param.eventSubscriptions = 1 << 17
        url = f'ws://{host}:{port}'
        if self.args.verbose >= 1:
            print(f'connecting to {url}...')
        try:
            ws = simpleobsws.WebSocketClient(url=url,
                                             password=password,
                                             identification_parameters=param)
            await ws.connect()
            await ws.wait_until_identified()
        except OSError as e:
            if self.args.daemon:
                return
            raise e
        ws.register_event_callback(self._on_active_state_changed, 'InputActiveStateChanged')
        self.ws = ws
        await self.check_state()

    def _update_last_received(self):
        self.last_received = datetime.datetime.now()

    async def _on_active_state_changed(self, data):
        self._update_last_received()
        name = data['inputName']
        active = data['videoActive']
        if self.args.verbose >= 1:
            print('InputActiveStateChanged {data}')
        if name in self.assigns:
            self.source_active_states[name] = active
            self.update_led()

    async def check_state(self):
        'Query if the sources are active and update the LED control'
        self._update_last_received()
        if self.args.verbose >= 2:
            print('check_state()...')
        for name in self.assigns:
            active = False
            try:
                req = simpleobsws.Request('GetSourceActive', {'sourceName': name})
                res = await self.ws.call(req)
                if not res.ok:
                    raise ValueError(f'Unexpected result for GetSourceActive: {res}')
                active = res.responseData['videoActive']
            except simpleobsws.NotIdentifiedError as e:
                if not self.args.daemon:
                    raise e
            except TypeError:
                # Probably the source was not found for some reason. Just ignore it.
                pass
            except Exception as e: # pylint: disable=W0718
                if not self.args.daemon:
                    raise e
                # pylint: disable=C0415
                import traceback
                traceback.print_exc()
            self.source_active_states[name] = active

        self.update_led()

    def clear_all(self):
        'Clear (turn-off) all LEDs.'
        for name in self.assigns:
            self.source_active_states[name] = False
        self.update_led()

    def update_led(self):
        'Update the LED'
        gpio_drives = {}
        for _, gpio in self.assigns.items():
            gpio_drives[gpio] = False

        for name, active in self.source_active_states.items():
            if active:
                gpio_drives[self.assigns[name]] = active

        for gpio, active in gpio_drives.items():
            if self.gpio_drives_prev[gpio] == active:
                continue
            GPIO.output(gpio, active)
        self.gpio_drives_prev = gpio_drives


def parse_arguments(argv=None):
    'Parse the arguments'
    parser = argparse.ArgumentParser(description = 'Tally light control using Raspberry PI GPIO')
    parser.add_argument('-c', '--connect', action='store', metavar='HOST:PORT',
                        help='obs-websocket server address')
    parser.add_argument('-a', '--assign', action='append', metavar='GPIO:SOURCE_NAME',
                        help='Assign the source to the GPIO')
    parser.add_argument('-d', '--daemon', action='store_true', default=False,
                        help='Run as a service')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Increase verbose level')
    return parser.parse_args(argv[1:] if argv else None)


async def mainloop(args):
    'The main loop'
    client = Tally(args)

    idle_check_time = datetime.timedelta(seconds=30)

    while True:
        if not client.ws or not client.ws.identified:
            try:
                host = args.connect.split(':')[0]
            except AttributeError:
                host = 'localhost'
            try:
                port = int(args.connect.split(':')[1])
            except AttributeError:
                port = 4455
            try:
                password = args.password
            except AttributeError:
                password = None
            await client.ws_connect(host, port, password)
        if client.ws and client.ws.identified:
            await asyncio.sleep(16)
            if datetime.datetime.now() - client.last_received > idle_check_time:
                await client.check_state()
        else:
            client.clear_all()
            await asyncio.sleep(4)


def main():
    'Entry point'
    args = parse_arguments()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(mainloop(args))


if __name__ == '__main__':
    main()
