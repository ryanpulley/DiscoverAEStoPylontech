# Discover AES batteries to Pylontech compatible inverter

![image](https://github.com/user-attachments/assets/34067a81-6ff9-407c-8231-5ed74aa4c1b0)

The Discover Lynk II gateway supports several brands of inverters, but lacks support for the Pylontech protocol which many inverters in the market have compatibility for.  This has forced those of us who own Discover AES batteries to use inverters from manufacturers which Discover Energy Systems has a development relationship with.  Alternatively, we could use an open loop (voltage based) configuration with non-supported inverters, but that has many operational disadvantages.

This solution allows owners of Discover AES batteries to choose from many available inverters in the market and benefit from a closed-loop integration.  It does this by reading packets from the Discover Lynk II gateway, transforms them, and then transmits to a Pylontech protocol compatible inverter.

A Raspberry PI with a dual port CAN adapter (CAN hat) are used with one port connected to the CAN port of the Lynk II gateway and the other connected to the BMS Port of the inverter.  The Lynk II gateway is configured to a protocol which Discover Energy Systems has published a protocol for.  The software reads this protocol CAN messages continuously from the Lynk II gateway.  It then transforms to Pylontech CAN messages and sends them to the inverter.

----------

## Additional Capabilities:
  -  Monitoring - The application emits all data fields via Lynk II to an MQTT broker which can be used for monitoring, alerting, visualization of battery metrics.  This data can easily be integrated into popular platforms such as Home Assistant.
  -  Cell Balancing / Absorb Charge - The application supports the capability to perform periodic "Cell Balancing" charges which frequency is configurable by the user (i.e. every 3 days).  It does this by "tricking" the inverter into thinking the batteries are not yet charged to 100% for a user configurable amount of time. 
  -  Logging - the application logs periodic key data to log files locally on the Raspberry PI

### Home Assistant dashboard example:

![image](https://github.com/user-attachments/assets/aed18531-8435-414c-a9ec-40b45485453f)

----------

## Requirements

  - Discover AES Batteries with a Lynk II Gateway - The application has been tested with the Discover AES Rackmount batteries and a Lynx II gateway but should work with any Discover AES battery.
  - A Raspberry PI 3B, 4 or 5 - preferrably with at least 4GB memory.  The application paired with an MQTT broker do not use much resource (memory or CPU) on the Raspberry PI.  However, I find the 2GB models to make simple desktop browsing and other tasks performance / reliability intolerable.
  - A 2 port CAN hat for the Raspberry PI.  I have used a [Waveshare 2-Channel CAN FD HAT](https://www.waveshare.com/2-ch-can-fd-hat.htm) with great success.
  - A Pylontech protocol compatible inverter.   I personnally use the Midnite MN15-12KW-AIO All in One inverter.
  - Cabling for connecting the Raspberry PI to the Lynk II and the Inverter.   I opted to wire the CAN Hat to a dual port RJ45 wall adapter and use standard CAT 5/6 cables to connect to the Lynk II gateway for a clean cabling approach.

Optional:
  - Home Assistant installation on your network.  The repository includes an example MQTT configuration for Home Assistant and sample dashboard.
  - A touch screen for your Raspberry PI.   I find it useful to have my Home Assistant dashboards always displayed near my inverter / batteries.

----------

## How to Use

Jump over to the [Wiki](https://github.com/ryanpulley/DiscoverAEStoPylontech/wiki) for detailed instructions on how to use the service.

----------

### _**>>   If you find value in this project please consider sponsoring to support my efforts [`Sponsor`](https://github.com/sponsors/ryanpulley) button on the right :+1:   <<**_
