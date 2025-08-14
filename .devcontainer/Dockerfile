FROM node:20-bullseye

# Install locales first and configure UTF-8
RUN apt-get update && apt-get install -y locales && \
    sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# Install system dependencies
RUN apt-get install -y \
    ca-certificates fonts-liberation libappindicator3-1 libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 \
    libexpat1 libfontconfig1 libgbm1 libgcc1 libglib2.0-0 libgtk-3-0 \
    libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 \
    libxss1 libxtst6 lsb-release wget xdg-utils xvfb fluxbox \
    x11vnc novnc websockify dbus-x11 x11-apps xterm net-tools \
    git build-essential curl \
    python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -O /tmp/chrome.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt install -y /tmp/chrome.deb && rm /tmp/chrome.deb

# Install pnpm globally
RUN npm install -g pnpm

# Create Chrome profile directory
RUN mkdir -p /workspace/chrome_profile && chmod 777 /workspace/chrome_profile

# Start container in /workspace
WORKDIR /workspace

EXPOSE 6080 9222
