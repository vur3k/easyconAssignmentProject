# DEMO Project
- Project can be ran using `docker compose -d --build [container-name [, ...]]`
- This project consists of 3 main components
  - MQTT circuit simulating automatic heating component
    | Device         | Role                                                                                                 |
    | -------------- | ---------------------------------------------------------------------------------------------------- |
    | thermometer.py | retrieves data from api, acts as a sensor that made the reading, publishes it to the broker          |
    | collector.py   | stores incoming messages from topics to db                                                           |
    | thermostat.py  | logical circuit which reacts to measured temperature, automatically turns on/off dependent radiators |
    | radiator.py    | reacting state machine                                                                               |
  - ModbusTCP server-client processing air-quality readings
    | Device             | Role                                                           |
    | ------------------ | -------------------------------------------------------------- |
    | air_quality_server | retrieves data from api, stores observed values into registers |
    | air_quality_client | reads data from registers, stores them into db                 |

  - Django layer
    - Offers endpoints to observe stored data
    - There is a makeshift state for management of the mqtt devices, which is not quite complete
