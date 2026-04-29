#
# NOTE: Use the Makefiles to build this image correctly.
#

ARG BASE_IMG=<base>
FROM $BASE_IMG

ARG TARGETARCH

USER root

# install - deadsnakes PPA for latest Python 3.11, openssh-server, generate host keys, create venv
RUN export DEBIAN_FRONTEND=noninteractive \
 && echo 'deb [trusted=yes] http://ppa.launchpad.net/deadsnakes/ppa/ubuntu jammy main' > /etc/apt/sources.list.d/deadsnakes.list \
 && apt-get -yq update \
 && apt-get -yq install --no-install-recommends \
    openssh-server \
    openssh-client \
    python3.11 \
    python3.11-venv \
    python3-pip \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /etc/ssh/sshd_config.d \
 && rm -f /etc/ssh/ssh_host_* \
 && ssh-keygen -t rsa -f /etc/ssh/ssh_host_rsa_key -N '' -b 4096 \
 && ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -N '' \
 && python3.11 -m venv /opt/ssh-proxy-venv \
 && /opt/ssh-proxy-venv/bin/pip install --no-cache-dir websockets

# sshd config
COPY --chown=root:root sshd_config.d/ssh-proxy.conf /etc/ssh/sshd_config.d/ssh-proxy.conf

# s6 - copy scripts
COPY --chown=${NB_USER}:${NB_GID} --chmod=755 s6/ /etc

# copy server code
COPY --chown=${NB_USER}:${NB_GID} server.py /opt/ssh-proxy/server.py

# sshd runs as root (needs to read host keys), websocket-proxy runs as NB_USER
# s6-overlay runs services as NB_USER by default; sshd/run uses s6-svcdir to override

EXPOSE 8888
