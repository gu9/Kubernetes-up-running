#!/bin/bash

# Replace these with your firewall and API credentials
FIREWALL="<firewall_IP_address>"
USERNAME="<api_username>"
PASSWORD="<api_password>"
API_KEY=$(curl -s -k -X GET "https://${FIREWALL}/api/?type=keygen&user=${USERNAME}&password=${PASSWORD}" | grep -o '<key>.*</key>' | sed 's/<\/\?key>//g')


# Replace these with your Panorama IP address and the number of hours for the key lifetime request
# Bootstrap vm-auth-key generate lifetime <1-8760>
KEY_LIFETIME="<number-of-hours>"

# Construct the API request URL
API_URL="https://${FIREWALL}/api/?type=op&key=${API_KEY}&cmd=<request><bootstrap><vm-auth-key><generate><lifetime><number-of-hours>${KEY_LIFETIME}</number-of-hours></lifetime></generate></vm-auth-key></bootstrap></request>"

# Make the API request and extract the vm-auth-key value using grep and sed
VM_AUTH_KEY=$(curl -s "${API_URL}" | grep -o '<vm-auth-key>.*</vm-auth-key>' | sed 's/<\/\?vm-auth-key>//g')

# Print the vm-auth-key value
echo "VM auth key: ${VM_AUTH_KEY}"
