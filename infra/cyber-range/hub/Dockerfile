# Cyber Range hub. NEEDS A PERSON'S REVIEW.
FROM quay.io/jupyterhub/jupyterhub:5.2.1
RUN python3 -m pip install --no-cache-dir dockerspawner==13.0.0 jupyterhub-idle-culler==1.4.0
COPY jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
WORKDIR /srv/jupyterhub
CMD ["jupyterhub", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
