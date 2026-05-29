#!/bin/bash

VERSION_CODENAME=$(awk -F= '$1=="VERSION_CODENAME" { print $2 ;}' /etc/os-release)

set_ubuntu_mirror() {
    truncate -s 0 /etc/apt/sources.list
    rm /etc/apt/sources.list.d/ubuntu.sources

    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME main restricted" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME-updates main restricted" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME universe" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME-updates universe" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME multiverse" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME-updates multiverse" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME-backports main restricted universe multiverse" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME-security main restricted" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME-security universe" | tee -a /etc/apt/sources.list
    echo "deb https://mirror.yandex.ru/ubuntu/ $VERSION_CODENAME-security multiverse" | tee -a /etc/apt/sources.list
}

set_pip_index_url() {
    pip config --global set global.index https://repo.sberned.ru/repository/pypi-public/pypi
    pip config --global set global.index-url https://repo.sberned.ru/repository/pypi-public/simple
    pip config --global set global.trusted-host repo.sberned.ru
}

install_common_packages() {
    apt -y update && apt-get install -y python3-pip python-is-python3 rsync p7zip-full p7zip-rar build-essential man-db mc htop nvtop
    wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
    dpkg -i cuda-keyring_1.1-1_all.deb
    apt-get update
    apt-get install -y cuda-toolkit-12-6
    unminimize
    apt clean
}

install_common_python_packages() {
    pip install --break-system-packages --no-cache-dir \
        poetry==1.8.5
}

set_ubuntu_mirror
install_common_packages
install_common_python_packages
set_pip_index_url
