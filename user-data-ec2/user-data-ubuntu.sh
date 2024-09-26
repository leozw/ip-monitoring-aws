#!/bin/bash

# Update packages and install Docker
sudo apt-get update -y
sudo apt-get install docker.io -y

# Add the ubuntu user to the docker group
sudo usermod -aG docker $USER

# Pull and run the IP monitoring container using Docker
sudo docker run -d -p 8000:8000 -e AWS_REGION="us-east-1,us-west-2,sa-east-1" leonardozwirtes/ip-monitoring-aws:latest

# Configure Docker to automatically start on boot
sudo systemctl enable docker
