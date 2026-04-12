#
# NOTE: Use the Makefiles to build this image correctly.
#

ARG BASE_IMG=<codeserver-python>
FROM $BASE_IMG

# disable timeout
ENV S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0
ENV NB_USER jovyan
ENV USERS_GID 100
ENV HOME /home/$NB_USER
ENV HOME_TMP /tmp_home/$NB_USER

USER root
COPY common.sh .
RUN chmod +x common.sh && ./common.sh && rm common.sh

COPY extensions /opt/vscode-extensions
COPY extensions.sh .
RUN chmod +x extensions.sh && ./extensions.sh && rm extensions.sh

RUN apt -y install fish micro && apt clean

RUN wget https://github.com/bootandy/dust/releases/download/v1.2.3/du-dust_1.2.3-1_amd64.deb && \
    dpkg -i du-dust_1.2.3-1_amd64.deb && \
    rm du-dust_1.2.3-1_amd64.deb

RUN wget https://github.com/jesseduffield/lazygit/releases/download/v0.54.2/lazygit_0.54.2_linux_x86_64.tar.gz && \
    tar xvf lazygit_0.54.2_linux_x86_64.tar.gz -C /usr/local/bin --wildcards lazygit && \
    rm lazygit_0.54.2_linux_x86_64.tar.gz

# NOTE: the contents of $HOME_TMP are copied to $HOME at runtime
#       this is a workaround because a PVC will be mounted at $HOME
#       and the contents of $HOME will be hidden
RUN cp -p -r -T ${HOME} ${HOME_TMP} \
    && chown -R ${NB_USER}:${USERS_GID} ${HOME_TMP}

USER $NB_USER
