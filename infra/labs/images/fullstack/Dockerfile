# Full-Stack profile: code-server (Open VSX marketplace, as the licence requires), Node.js and the psql client.
FROM quay.io/jupyter/base-notebook:python-3.11
ARG CODE_SERVER_VERSION=4.95.3
USER root
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm postgresql-client git curl \
    && curl -fsSL "https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server_${CODE_SERVER_VERSION}_amd64.deb" -o /tmp/cs.deb \
    && apt-get install -y /tmp/cs.deb && rm /tmp/cs.deb \
    && rm -rf /var/lib/apt/lists/*
USER ${NB_UID}
RUN python3 -m pip install --no-cache-dir jupyter-vscode-proxy==0.6
WORKDIR /home/jovyan
