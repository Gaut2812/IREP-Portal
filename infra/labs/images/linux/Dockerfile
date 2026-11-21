# Linux sandbox profile: JupyterLab terminal with everyday CLI tools. Runs as uid 1000, no sudo.
FROM quay.io/jupyter/base-notebook:python-3.11
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      git vim nano less tree curl wget zip unzip jq htop man-db procps iputils-ping \
    && rm -rf /var/lib/apt/lists/*
USER ${NB_UID}
WORKDIR /home/jovyan
