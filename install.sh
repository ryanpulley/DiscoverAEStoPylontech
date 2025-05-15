#!/bin/bash

# Set variables
REPO_URL="https://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@github.com/ryanpulley/DiscoverAEStoPylontech.git"
APP_NAME="DiscoverBMS"
INSTALL_DIR=~/$APP_NAME
OS_USER=`whoami`
FIRMWARE_CONFIG_FILE=/boot/firmware/config.txt


# Function to search for a specific entry in a config file
search_config() {
  config_file="$1"
  search_term="$2"

  # Check if the config file exists
  if [[ ! -f "$config_file" ]]; then
    return 1
  fi

  # Search for the entry using grep
  if grep -q "$search_term" "$config_file"; then
    return 0
  else
    return 1
  fi
}

# Function to add waveshare configs
WaveShare_config() {
  config_file=$1
  cat <<EOF | sudo tee -a $1
dtparam=spi=on
dtoverlay=spi1-3cs
dtoverlay=mcp251xfd,spi0-0,interrupt=25
dtoverlay=mcp251xfd,spi1-0,interrupt=24
EOF
}


echo "$(date) : searching for WaveShare CAN FD HAT configs"
# Check WaveShare configs
if search_config ${FIRMWARE_CONFIG_FILE} "dtoverlay=mcp251xfd"; then
  echo "$(date) : WaveShare CAN FD HAT firmware configs found"
else
  echo "$(date) : No WaveShare CAN FD HAT firmware configs found"
  echo "Do you wish to install WaveShare CAN FD HAT firmware configs and reboot?(Y/N)"
  select yn in "Y" "N"; do
    case $yn in
      [Yy]* ) WaveShare_config ${FIRMWARE_CONFIG_FILE}; sudo reboot; break;;
      [Nn]* ) break;; 
    esac
  done
fi

echo "$(date) : installing mosquitto and CAN utilities"
sudo apt install can-utils mosquitto mosquitto-clients

echo "$(date) : cloning DiscoverBMS repository to ${INSTALL_DIR}"
# Clone the repository
git clone $REPO_URL $INSTALL_DIR

# Change directory to the application directory
cd $INSTALL_DIR

echo "$(date) : creating python virtual environment"
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

echo "$(date) : installing python dependencies"
# Install dependencies
pip install -r requirements.txt 

echo "$(date) : creating log directory"
# Create a directory for logs
mkdir -p ${INSTALL_DIR}/log

echo "$(date) : creating systemd services"
sudo rm /etc/systemd/system/${APP_NAME}-CAN.service
#cat <<EOF |sudo tee -a /etc/systemd/system/${APP_NAME}-CAN.service
sudo bash -c "cat <<EOF > /etc/systemd/system/${APP_NAME}-CAN.service
[Unit]
Description=${APP_NAME} CAN Initialization Service
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=${INSTALL_DIR}/startcan.sh
WorkingDirectory=${INSTALL_DIR}
User=${OS_USER}
StandardOutput=append:${INSTALL_DIR}/log/${APP_NAME}-CAN.service.log
StandardError=append:${INSTALL_DIR}/log/${APP_NAME}-CAN.service.log

[Install]
WantedBy=multi-user.target
EOF
"

sudo rm /etc/systemd/system/${APP_NAME}.service
#cat <<EOF |sudo tee -a /etc/systemd/system/${APP_NAME}.service
sudo bash -c "cat <<EOF > /etc/systemd/system/${APP_NAME}.service
[Unit]
Description=${APP_NAME} Service
After=${APP_NAME}-CAN.service
Wants=network-online.target

[Service]
Restart=always
RestartSec=10
User=${OS_USER}
ExecStart=${INSTALL_DIR}/start.sh
WorkingDirectory=${INSTALL_DIR}
User=${OS_USER}
StandardOutput=append:${INSTALL_DIR}/log/${APP_NAME}.service.log
StandardError=append:${INSTALL_DIR}/log/${APP_NAME}.service.log

[Install]
WantedBy=multi-user.target
EOF
"

echo "$(date) : enabling and starting systemd services"
# Enable and start the service (optional)
sudo systemctl daemon-reload
sudo systemctl enable ${APP_NAME}-CAN.service
sudo systemctl start ${APP_NAME}-CAN.service

sudo systemctl enable ${APP_NAME}.service
sudo systemctl start ${APP_NAME}.service

echo "$APP_NAME installed successfully!"
