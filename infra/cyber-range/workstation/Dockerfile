# Student workstation for the Cyber Range: JupyterLab terminal with web-testing tools. Runs as uid 1000.
FROM quay.io/jupyter/base-notebook:python-3.11
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl wget nmap sqlmap nikto dnsutils iputils-ping netcat-openbsd jq \
    && rm -rf /var/lib/apt/lists/*
USER ${NB_UID}
RUN printf '%s\n' "Targets on this range: http://juice-shop:3000 and http://dvwa" "Only these hosts exist here. Your use is logged and covered by the AUP you signed." > /home/jovyan/README-RANGE.txt
WORKDIR /home/jovyan
