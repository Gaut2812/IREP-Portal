# Docker & Kubernetes profile (labs track S11). NEEDS A PERSON'S REVIEW.
# Runs ONLY with the Sysbox runtime (sysbox-runc) on a lab node that has Sysbox installed:
# Docker and kind work inside the container without --privileged, because Sysbox maps the
# container's root to an unprivileged user on the host. The hub refuses this profile when
# LAB_SYSBOX is not "1" (jupyterhub_config.py).
FROM quay.io/jupyter/base-notebook:python-3.11
ARG KIND_VERSION=v0.24.0
ARG KUBECTL_VERSION=v1.31.2
USER root
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg iptables \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io \
    && curl -fsSLo /usr/local/bin/kind "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-amd64" \
    && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kind /usr/local/bin/kubectl \
    && usermod -aG docker ${NB_USER} \
    && rm -rf /var/lib/apt/lists/*
# images come only through the lab network's pull-through cache (no other egress)
COPY daemon.json /etc/docker/daemon.json
COPY kind-config.yaml /etc/irep/kind-config.yaml
COPY start-dockerd.sh /usr/local/bin/before-notebook.d/10-start-dockerd.sh
# docker-stacks start.sh runs before-notebook.d hooks as root, then drops to jovyan (NB_UID 1000)
ENV NB_USER=jovyan CHOWN_HOME=no
WORKDIR /home/jovyan
