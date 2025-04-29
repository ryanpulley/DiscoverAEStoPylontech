Discover AES batteries to Pylontech compatible inverter

![image](https://github.com/user-attachments/assets/34067a81-6ff9-407c-8231-5ed74aa4c1b0)

The Discover Lynx II gateway supports several brands of inverters, but lacks support for the Pylontech protocol which many inverters in the market support.  This has forced those of us who own Discover AES batteries to use inverters from manufacturers which Discover Energy Systems has a development relationship with.  Alternatively, we could use an open loop (voltage based) configuration with non-supported inverters, but that has many operational disadvantages.

This solution allows owners of Discover AES batteries to choose from many available inverters in the market and benefit from a closed-loop integration.  It does this by reading packets from the Discover Lynx II gateway, transform them, and send them to a Pylontech protocol compatible inverter.

We use a Raspberry PI with a dual port CAN adapter (CAN hat) which one port connected to the CAN port of the Lynx II gateway and the other connected to the BMS Port of the inverter.  The Lynx II gateway is configured to a protocol which Discover Energy Systems has published a protocol for.  The software reads this protocol CAN messages continuously from the Lynx II gateway.  It then transforms to Pylontech CAN messages and sends them to the inverter.

Additional Capabilities:
  -  Cell Balancing / Absorb Charge - The application supports the capability to perform periodic "Cell Balancing" charges which frequency is configurable by the user (i.e. every 3 days).  It does this by "tricking" the inverter into thinking the batteries are not yet charged to 100% for a user configurable amount of time. 
  -  Monitoring - The application emits all data fields via Lynx II to an MQTT broker which can be used for monitoring, alerting, visualization of battery metrics.  This data can easily be integrated into popular platforms such as Home Assistant.
  -  Logging - the application logs periodic key data to log files locally on the Raspberry PI
