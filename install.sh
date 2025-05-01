#!/bin/bash

# Set variables
REPO_URL="<repository_url>"
APP_NAME="<app_name>"
INSTALL_DIR="/opt/$APP_NAME"

# Clone the repository
git clone $REPO_URL $INSTALL_DIR

# Change directory to the application directory
cd $INSTALL_DIR

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create a directory for logs (optional)
mkdir -p /var/log/$APP_NAME

# Create a systemd service file (optional)
cat <<EOF > /etc/systemd/system/$APP_NAME.service
[Unit]
Description=$APP_NAME application
After=network.target

[Service]
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python <main_script>.py
User=<user>
Group=<group>
Restart=on-failure
StandardOutput=append:/var/log/$APP_NAME/output.log
StandardError=append:/var/log/$APP_NAME/error.log

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service (optional)
systemctl enable $APP_NAME
systemctl start $APP_NAME

echo "$APP_NAME installed successfully!"