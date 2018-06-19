import appdaemon.plugins.hass.hassapi as hass
import threading
import time, datetime

### Comments ###

### Args ###
"""
# switch_id: {entity_id of switch}
# light_id: {entity_id of light}
# delay: {1 = one second. Can go below 1 second. Anything below 0.4 was not working well for me}
# on_off_delay: delay for a "short" click which will turn on/off the light (no dimming)
# step: {how many brightness steps to go up/down per change}
# minimum: {brightness to go to. Lowest = 0}
# maximum:{brightness to go to. Highest = 255}

EXAMPLE appdaemon.yaml entry:

adams_bedside_light_switch_LCB:
  module: lights_cycle_brightness
  class: Lights_Cycle_Brightness
  switch_id: binary_sensor.switch_158
  light_id: light.bedside_one
  delay: 0.4
  on_off_delay: 0.4
  step: 25
  minimum: 25
  maximum: 250
"""

class Lights_Cycle_Brightness(hass.Hass):
    def initialize(self):
        self.log("LCB Started.")
        self.going_up = True

        self.delay = float(self.args["delay"])
        self.on_off_delay = float(self.args["on_off_delay"])
        self.minimum = int(self.args["minimum"])
        self.maximum = int(self.args["maximum"])
        self.step = int(self.args["step"])
        self.switch_id = self.args["switch_id"]
        self.light_id = self.args["light_id"]
        
        for switch in self.split_device_list(self.switch_id):
            self.listen_state(self.start_func, switch)


    def start_func(self, entity, attributes, old, new, kwargs):
        if new == "on":
            # Down
            self.last_on_time = datetime.datetime.now()
            self.t = threading.Thread(target=self.run_thread, args=(entity,))
            self.t.start()
        else:
            # Release

            # If released shortly, act as a standard toggle switch
            if (datetime.datetime.now() - self.last_on_time).total_seconds() < self.on_off_delay:
                self.call_service("light/toggle", entity_id = self.light_id)

    def run_thread(self, switch):

        # Initial delay
        time.sleep(self.on_off_delay)

        while(self.get_state(switch) == "on"):
            if self.get_state(self.light_id) == "off":
                self.turn_on(self.light_id)

            try:
                self.brightness = int(self.get_state(entity = self.light_id, attribute = "brightness")) # get lights current brightness
            except:
                while(self.brightness == None and self.get_state(switch) == "on"):
                    try:
                        self.brightness = int(self.get_state(entity = self.light_id, attribute = "brightness"))
                    except:
                        pass

            if self.going_up:
                self.brightness += self.step
                if self.brightness > self.maximum:
                    self.brightness = self.maximum
                    self.going_up = False
            else:
                self.brightness = self.brightness - self.step
                if self.brightness < self.minimum:
                    self.brightness = self.minimum
                    self.going_up = True

            #self.log("{} changed to brightness: {}".format(self.light_id, self.brightness))

            self.turn_on(self.light_id, brightness=self.brightness)
            time.sleep(self.delay)
