#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

cd google-base
docker build -t clusterinthecloud/google-base:latest .

cd ../google-install
docker build -t clusterinthecloud/google-install:latest .

cd ../google-destroy
docker build -t clusterinthecloud/google-destroy:latest .
