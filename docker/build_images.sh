#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

if command -v podman; then
	DOCKER=podman
else
	DOCKER=docker
fi

cd google-base
$DOCKER build -t clusterinthecloud/google-base:latest .

cd ../google-install
$DOCKER build -t clusterinthecloud/google-install:latest .

cd ../google-destroy
$DOCKER build -t clusterinthecloud/google-destroy:latest .
