FROM ubuntu:22.04
ARG S6_VERSION=v2.2.0.3
ARG S6_ARCH=amd64
ARG DEBIAN_FRONTEND=noninteractive
ARG USER_NAME=pagermaid
ARG WORK_DIR=/pagermaid/workdir
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    SHELL=/bin/bash \
    LANG=zh_CN.UTF-8 \
    PS1="\u@\h:\w \$ " \
    RUN_AS_ROOT=true
SHELL ["/bin/bash", "-c"]
WORKDIR $WORK_DIR

# ===== 1. 源码编译安装 Python3.6 =====
RUN apt-get update && apt-get install -y \
    wget build-essential \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libffi-dev libncurses5-dev libncursesw5-dev \
    liblzma-dev tk-dev

RUN wget https://www.python.org/ftp/python/3.6.15/Python-3.6.15.tgz \
    && tar -xf Python-3.6.15.tgz \
    && cd Python-3.6.15 \
    && ./configure --enable-optimizations \
    && make -j$(nproc) \
    && make altinstall \
    && cd .. && rm -rf Python-3.6.15*

# 建议只链接 python3.6/pip3.6，避免覆盖系统python3
RUN ln -sf /usr/local/bin/python3.6 /usr/bin/python3.6 \
    && ln -sf /usr/local/bin/pip3.6 /usr/bin/pip3.6

# ===== 2. 你的原有依赖安装和环境配置 =====
RUN source ~/.bashrc \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-chi-sim \
        language-pack-zh-hans \
        sudo \
        git \
        openssl \
        redis-server \
        curl \
        wget \
        neofetch \
        imagemagick \
        ffmpeg \
        fortune-mod \
        figlet \
        libmagic1 \
        libzbar0 \
        iputils-ping \
    ## 安装s6
    && curl -L -o /tmp/s6-overlay-installer https://github.com/just-containers/s6-overlay/releases/download/${S6_VERSION}/s6-overlay-${S6_ARCH}-installer \
    && chmod +x /tmp/s6-overlay-installer \
    && /tmp/s6-overlay-installer / \
    ## 安装编译依赖
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        apt-utils \
        libxslt1-dev \
        libxml2-dev \
        libssl-dev \
        libffi-dev \
        zlib1g-dev \
        tcl8.6-dev \
        tk8.6-dev \
        libimagequant-dev \
        libraqm-dev \
        libjpeg-dev \
        libtiff5-dev \
        libopenjp2-7-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libwebp-dev \
        python3-tk \
        libharfbuzz-dev \
        libfribidi-dev \
        libxcb1-dev \
        pkg-config \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    ## 添加用户
    && useradd $USER_NAME -u 917 -U -r -m -d /$USER_NAME -s /bin/bash \
    && usermod -aG sudo,users $USER_NAME \
    && echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER_NAME \
    ## 克隆仓库
    && git clone -b master https://github.com/Jejz168/PagerMaid-Modify.git $WORK_DIR \
    && git config --global pull.ff only \
    ## 复制s6启动脚本
    && cp -r s6/* /

# ===== 3. pip 安装依赖，务必用python3.6 =====
RUN python3.6 -m pip install --upgrade pip \
    && python3.6 -m pip install -r requirements.txt

# ===== 4. 清理依赖和缓存 =====
RUN apt-get purge --auto-remove -y \
        build-essential \
        apt-utils \
        libxslt1-dev \
        libxml2-dev \
        libssl-dev \
        libffi-dev \
        zlib1g-dev \
        tcl8.6-dev \
        tk8.6-dev \
        libimagequant-dev \
        libraqm-dev \
        libjpeg-dev \
        libtiff5-dev \
        libopenjp2-7-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libwebp-dev \
        python3-tk \
        libharfbuzz-dev \
        libfribidi-dev \
        libxcb1-dev \
        pkg-config \
    && apt-get clean -y \
    && rm -rf /tmp/* /var/lib/apt/lists/* /var/tmp/* ~/.cache

ENTRYPOINT ["/init"]
