# Discover AES batteries to Pylontech compatible inverter

![image](https://github.com/user-attachments/assets/34067a81-6ff9-407c-8231-5ed74aa4c1b0)

The Discover Lynx II gateway supports several brands of inverters, but lacks support for the Pylontech protocol which many inverters in the market have compatibility for.  This has forced those of us who own Discover AES batteries to use inverters from manufacturers which Discover Energy Systems has a development relationship with.  Alternatively, we could use an open loop (voltage based) configuration with non-supported inverters, but that has many operational disadvantages.

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

### Installing the Raspberry PI

#### Install the CAN Hat
Note that CAN hats do not typically fit in standard Raspberry PI cases.  As I use a touchscreen display, I have no need for a case as the Raspberry PI mounts on the back of the display.  If you choose to go "headless", there are some larger cases available that will accomodate the PI and the CAN Hat.  

I use the [Waveshare 2-Channel CAN FD HAT](https://www.waveshare.com/2-ch-can-fd-hat.htm).  I highly recommend installing the CAN adapter standoffs that come with the board to stablize and avoid putting pressure on the pins with pulling cables, etc.

#### Configure the Raspberry PI OS
_The instructions below start from a freshly imaged SD card for a Raspberry PI 5 with the "Raspberry Pi OS (64-Bit) --- Debian Bookworm" image and basic configuration completed (network, accounts, timezone, initial software updates, etc.)._


1) From a terminal window, download the install script into your home directory

  ```curl -s -O https://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@raw.githubusercontent.com/ryanpulley/DiscoverAEStoPylontech/refs/heads/main/install.sh```

2) Run the install script as the user that you wish to install the service as:

  ```./install.sh```

  _Note: If this is the first time the install has been run on the Raspberry PI, it will reboot after installing the Waveshare CAN FD Hat firmware configs.   After the reboot, start the install script again._

  - This install script does the following:

    - Enables the Waveshare CAN FD Hat firmware configs if not already enabled and reboots
    - Installs MQTT - Mosquitto and client (mosquitto, mosquitto-client)
    - Installs the CAN Utilities (can-utils)
    - Configures Mosquitto (/etc/mosquitto/mosquitto.conf) for out of localhost listener
    - Makes a backup of the current service to [directory.backup]
    - Clones the DiscoverBMS repository to your Raspberry PI under the users home directory (~/DiscoverBMS)
    - Creates a Python Virtual Environment
    - Installs all Python packages required by the service
    - Creates a log directory in the DiscoverBMS directory for service logs
    - Creates systemd services for initializing the CAN ports and the DiscoverBMS service
    - Reloads the systemd daemon to recognize these new services
    - Starts the systemd services

### Configuring the Discover Lynk II gateway
#### Jumper Settings
![IMG_5085](https://github.com/user-attachments/assets/43248775-edf4-469c-aa04-b6aff3ba7165)


#### Protocol Configuration
![IMG_5085](https://github.com/user-attachments/assets/93b5cca7-ce0b-4620-aa94-6fb4b4d9277b)


You can configure the Discover Lynx II gateway with the Lynx Access windows application with a serial connection via a USB cable from a windows machine to the gateway.  Recently, Discover has enabled the ethernet connectivity from the Lynx II gateway (Lynx Firmware release 2.1+).  You can also configure the protocol from the Discover cloud app when registered and enabled.

These instructions show how to configure from the Windows Lynx Access application.

### Connecting the CAN Hat to the Lynk II gateway
### Connecting the CAN Hat to the Inverter

