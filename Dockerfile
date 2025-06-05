FROM ubuntu:22.04

ARG S6_VERSION=v2.2.0.3
ARG S6_ARCH=amd64
ARG USER_NAME=pagermaid
ARG WORK_DIR=/pagermaid/workdir
ARG DEBIAN_FRONTEND=noninteractive

ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    SHELL=/bin/bash \
    LANG=zh_CN.UTF-8 \
    PS1="\u@\h:\w \$ " \
    RUN_AS_ROOT=true

SHELL ["/bin/bash", "-c"]

WORKDIR $WORK_DIR

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        wget \
        curl \
        git \
        sudo \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        libncursesw5-dev \
        libgdbm-dev \
        libc6-dev \
        libffi-dev \
        uuid-dev \
        liblzma-dev \
        tk-dev \
        redis-server \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-chi-sim \
        language-pack-zh-hans \
        imagemagick \
        ffmpeg \
        libmagic1 \
        libzbar0 \
        iputils-ping \
        neofetch \
        fortune-mod \
        figlet \
    && curl -L -o /tmp/s6-overlay-installer https://github.com/just-containers/s6-overlay/releases/download/${S6_VERSION}/s6-overlay-${S6_ARCH}-installer \
    && chmod +x /tmp/s6-overlay-installer \
    && /tmp/s6-overlay-installer / \
    && wget https://www.python.org/ftp/python/3.6.15/Python-3.6.15.tgz -O /tmp/Python-3.6.15.tgz \
    && tar xzf /tmp/Python-3.6.15.tgz -C /tmp \
    && cd /tmp/Python-3.6.15 \
    && ./configure --enable-optimizations \
    && make -j$(nproc) \
    && make altinstall \
    && cd / \
    && rm -rf /tmp/Python-3.6.15 /tmp/Python-3.6.15.tgz \
    && ln -sf /usr/local/bin/python3.6 /usr/bin/python3 \
    && ln -sf /usr/local/bin/python3.6 /usr/bin/python \
    && python3 -m pip install --upgrade pip setuptools wheel \
    && useradd $USER_NAME -u 917 -U -r -m -d /$USER_NAME -s /bin/bash \
    && usermod -aG sudo,users $USER_NAME \
    && echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER_NAME \
    && git clone -b master https://github.com/Jejz168/PagerMaid-Modify.git $WORK_DIR \
    && pip install -r $WORK_DIR/requirements.txt \
    && apt-get purge -y --auto-remove build-essential wget curl git sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* ~/.cache

ENTRYPOINT ["/init"]
