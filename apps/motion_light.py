import appdaemon.plugins.hass.hassapi as hass
import enum

### Args ###
"""
    switches: manual switch device(s) (a switch will toggle light status when switching state) (O)
    pushbuttons: manual pushbutton device(s) (a pushbutton will toggle light status when turned on) (O)
    motion_sensors: motion detector(s) (supposed to be on when motion detected) (O)
    motion_delay: delay (in s) to keep the light on after motion; if not specified light won't be turned off; if 0, light will turn off when motion stops (O)
    illumination_sensor: illumination sensor device (O)
    illumination_max: max illumination so that motion turns light on (unit should be the same as the sensor) (O)
    exit_delay: delay (in s) after a manual turn off during which any motion is ignored (so that it doesn't turn the light back on when exiting the room) (O)

    light: light (or any switchable device) to control. If multiple lights are to be controlled, a light group must be created and specified here (M)

    debug: yes/no to enable debugging

"""

class Motion_Light_Switch(hass.Hass):

    class State(enum.Enum):
        ON = enum.auto()
        ON_TIMER = enum.auto()   # Light on
        OFF = enum.auto()
        EXIT_TIMER = enum.auto()    # Light off

    def initialize(self):

        self._debug = True if "debug" in self.args and self.args["debug"] else False

        if self._debug:
            self.log("Motion_Light_Switch startup")

        self._light = self.args["light"]

        self._switches = self.split_device_list(self.args["switches"]) if "switches" in self.args else []
        for switch in self._switches:
            # Listen to any state change
            self.listen_state(self.manual_toggle_cb, switch)

        self._pushbuttons = self.split_device_list(self.args["pushbuttons"]) if "pushbuttons" in self.args else []
        for pb in self._pushbuttons:
            # Listen only to ON event
            self.listen_state(self.manual_toggle_cb, pb, new="on")

        self._motion_sensors = self.split_device_list(self.args["motion_sensors"]) if "motion_sensors" in self.args else []
        for sensor in self._motion_sensors:
            # Listen to any state change
            self.listen_state(self.motion_cb, sensor)

        self._illumination_sensor = self.args["illumination_sensor"] if "illumination_sensor" in self.args else None
        if self._illumination_sensor:
            self.listen_state(self.illumination_cb, self._illumination_sensor)

        self._illumination_max = float(self.args["illumination_max"]) if "illumination_max" in self.args else 0

        self._motion_delay = float(self.args["motion_delay"]) if "motion_delay" in self.args else None
        self._exit_delay = float(self.args["exit_delay"]) if "exit_delay" in self.args else 0

        self._exit_timer = None
        self._motion_timer = None

        self._state = self.State.ON if self.get_state(self._light) == "on" else self.State.OFF

        if self._debug:
            self.log("Motion_Light_Switch startup done")


    def manual_toggle_cb(self, entity, attributes, old, new, kwargs):

        if self._debug:
            self.log ("toggle_cb state %s new %s" % (self._state, new))

        if self._state == self.State.ON:
            self.turn_off(self._light)
            self.run_in(self.exit_delay_cb, self._exit_delay)
            self._state = self.State.EXIT_TIMER

        elif self._state == self.State.OFF:
            self.turn_on(self._light)
            self._state = self.State.ON

        elif self._state == self.State.ON_TIMER:
            self.turn_off(self._light)
            self.cancel_timer(self._motion_timer)
            self.run_in(self.exit_delay_cb, self._exit_delay)
            self._state = self.State.EXIT_TIMER

        elif self._state == self.State.EXIT_TIMER:
            self.turn_on(self._light)
            self.cancel_timer(self._exit_timer)
            self._state = self.State.ON

        else:
            raise RuntimeError("Invalid state %s" % repr(self._state))

        if self._debug:
            self.log("toggle_cb out state %s" % (self._state))

    def exit_delay_cb(self, kwargs):

        if self._debug:
            self.log ("exit_delay_cb state %s" % (self._state))

        if self._state == self.State.EXIT_TIMER:
            self._state = self.State.OFF
        else:
            raise RuntimeError("Invalid state %s" % repr(self._state))

        if self._debug:
            self.log("exit_delay_cb out state %s" % (self._state))

    def motion_delay_cb(self, kwargs):

        if self._debug:
            self.log ("motion_delay_cb state %s" % (self._state))

        if self._state == self.State.ON_TIMER:
            self.turn_off(self._light)
            self._state = self.State.OFF
        else:
            raise RuntimeError("Invalid state %s" % repr(self._state))

        if self._debug:
            self.log("motion_delay_cb out state %s" % (self._state))

    def motion_cb(self, entity, attributes, old, new, kwargs):

        if self._debug:
            self.log ("motion_cb state %s new %s" % (self._state, new))

        if new == "on":
            if self._state in (self.State.ON_TIMER, self.State.ON):
                pass

            elif self._state == self.State.OFF:
               
                # Check illumination
                if self._illumination_sensor is None or self._illumination_max is None \
                    or self.get_state(self._illumination_sensor) <= self._illumination_max:
                    # Turn ON
                    self.turn_on(self._light)
                    self._state = self.State.ON

            elif self._state == self.State.EXIT_TIMER:
                # Don't turn ON during exit timer
                pass

            else:
                raise RuntimeError("Invalid state %s" % repr(self._state))
        else:

            if self._state == self.State.ON_TIMER:
                # Reinit timer
                self.cancel_timer(self._motion_timer)
                self._motion_timer = self.run_in(self.motion_delay_cb, self._motion_delay)
                self._state = self.State.ON_TIMER

            elif self._state == self.State.ON:
                # Start timer
                if self._motion_delay is None:
                    # No timer, no off
                    pass
                elif self._motion_delay == 0:
                    # Turn off immediately
                    self.turn_off(self._light)
                    self._state = self.State.OFF
                else:
                    # Start timer
                    self._motion_timer = self.run_in(self.motion_delay_cb, self._motion_delay)
                    self._state = self.State.ON_TIMER

            elif self._state == self.State.OFF:
                pass

            elif self._state == self.State.EXIT_TIMER:
                pass

            else:
                raise RuntimeError("Invalid state %s" % repr(self._state))

        if self._debug:
            self.log("motion_cb out state %s" % (self._state))
