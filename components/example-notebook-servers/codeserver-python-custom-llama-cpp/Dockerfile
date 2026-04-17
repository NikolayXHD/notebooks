#
# NOTE: Use the Makefiles to build this image correctly.
#

ARG BASE_IMG=<codeserver-python-custom>
FROM $BASE_IMG

USER root

RUN apt -y update \
    && apt install libnvidia-compute-590 \
    && wget -nv https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin \
    && cp cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600 \
    && wget -nv https://developer.download.nvidia.com/compute/cuda/13.1.0/local_installers/cuda-repo-ubuntu2204-13-1-local_13.1.0-590.44.01-1_amd64.deb \
    && dpkg -i cuda-repo-ubuntu2204-13-1-local_13.1.0-590.44.01-1_amd64.deb \
    && cp /var/cuda-repo-ubuntu2204-13-1-local/cuda-*-keyring.gpg /usr/share/keyrings/ \
    && apt -y update \
    && DEBIAN_FRONTEND=noninteractive apt -y install cuda-toolkit-13-1 \
    && rm cuda-repo-ubuntu2204-13-1-local_13.1.0-590.44.01-1_amd64.deb cuda-ubuntu2204.pin /var/cuda-repo-ubuntu2204-13-1-local/*.deb \
    && apt clean

USER $NB_USER
