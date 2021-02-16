# am43mqtt
Python script that can run on Raspberry pi (Zero W) with MQTT. Base Code coming from https://github.com/TheBazeman/A-OK-AM43-Blinds-Drive

I have remove HTTP and add MQTT that can communicate with Homa Assistans MQTT Cover https://www.home-assistant.io/integrations/cover.mqtt/

Install libraries needed: sudo pip3 install bluepy, retrying, paho-mqt


Eg. on home assistant cover config.
```
cover:
  - platform: mqtt
    command_topic: "homeblind/Blinds1/set"
    position_topic: "homeblind/Blinds1/position"
    set_position_topic: "homeblind/Blinds1/set_position"
    position_open: 0
    position_closed: 100```
