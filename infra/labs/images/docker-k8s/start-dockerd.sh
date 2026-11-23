#!/bin/bash
# Runs as root inside the Sysbox container (root here is an unprivileged uid on the host).
dockerd >/var/log/dockerd.log 2>&1 &
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
