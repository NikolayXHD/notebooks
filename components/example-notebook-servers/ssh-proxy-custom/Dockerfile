#
# NOTE: Use the Makefiles to build this image correctly.
#

ARG BASE_IMG=<ssh-proxy>
FROM $BASE_IMG

ARG TARGETARCH

# disable timeout
ENV S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0
ENV NB_USER jovyan
ENV USERS_GID 100
ENV HOME /home/$NB_USER
ENV HOME_TMP /tmp_home/$NB_USER

USER root
COPY common.sh .
RUN chmod +x common.sh && ./common.sh && rm common.sh

RUN apt -y update && apt -y install fish micro sudo direnv && apt clean

# passwordless su (jovyan → root) via PAM
RUN awk -v nb_user="$NB_USER" 'match($0, /auth[[:space:]]+sufficient[[:space:]]+pam_rootok\.so/) {print $0 ORS "auth       sufficient pam_succeed_if.so use_uid user = " nb_user; next} {print}' /etc/pam.d/su > /tmp/su && mv /tmp/su /etc/pam.d/su

# passwordless sudo
RUN echo "$NB_USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/$NB_USER && chmod 0440 /etc/sudoers.d/$NB_USER

RUN wget https://github.com/bootandy/dust/releases/download/v1.2.3/du-dust_1.2.3-1_amd64.deb && \
    dpkg -i du-dust_1.2.3-1_amd64.deb && \
    rm du-dust_1.2.3-1_amd64.deb

RUN wget https://github.com/jesseduffield/lazygit/releases/download/v0.54.2/lazygit_0.54.2_linux_x86_64.tar.gz && \
    tar xvf lazygit_0.54.2_linux_x86_64.tar.gz -C /usr/local/bin --wildcards lazygit && \
    rm lazygit_0.54.2_linux_x86_64.tar.gz

RUN curl -Lso /tmp/uv.tar.gz https://github.com/astral-sh/uv/releases/download/0.6.15/uv-x86_64-unknown-linux-gnu.tar.gz && \
    tar xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 && \
    rm /tmp/uv.tar.gz

# direnv + PermitUserEnvironment for transparent SSH env
RUN echo "PermitUserEnvironment yes" >> /etc/ssh/sshd_config && \
    mkdir -p ${HOME}/.ssh ${HOME}/.config/direnv && \
    echo "BASH_ENV=${HOME}/.bash_env" > ${HOME}/.ssh/environment && \
    chmod 600 ${HOME}/.ssh/environment && \
    echo '[global]' > ${HOME}/.config/direnv/direnv.toml && \
    echo 'load_dotenv = true' >> ${HOME}/.config/direnv/direnv.toml && \
    printf '%s\n' \
        'if command -v direnv >/dev/null 2>&1' \
        'then' \
        '    if [ -f "$HOME/git/dc/mess/.envrc" ]' \
        '    then' \
        '        cd "$HOME/git/dc/mess"' \
        '        eval "$(direnv export bash 2>/dev/null)"' \
        '    fi' \
        'fi' \
        > ${HOME}/.bash_env && \
    chown -R ${NB_USER}:${USERS_GID} ${HOME}/.ssh ${HOME}/.config ${HOME}/.bash_env

# NOTE: the contents of $HOME_TMP are copied to $HOME at runtime
#       this is a workaround because a PVC will be mounted at $HOME
#       and the contents of $HOME will be hidden
RUN cp -p -r -T ${HOME} ${HOME_TMP} \
    && chown -R ${NB_USER}:${USERS_GID} ${HOME_TMP}
