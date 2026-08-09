ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:3.19
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# libGammu is built from source rather than installed from apk so the SMS prompt
# fix can be applied. Alpine's gammu only recognises an SMS prompt of "> ", which
# stalls GSM_SendSMS on modems emitting a bare ">" (eg. SIMCom SIM7670G).
#
# The patch is fetched from the open upstream pull request rather than vendored,
# so there is exactly one source of truth. When that PR is merged the build fails
# on purpose -- see the guard below -- forcing a move to a released gammu instead
# of quietly carrying a patch that is no longer needed.
#
# GAMMU_VERSION must satisfy GAMMU_REQUIRED in python-gammu's setup.py, which is
# 1.44.0 as of python-gammu 3.4.0. Building the sdist against anything older
# fails with "Can not find supported Gammu version using pkg-config!".
ARG GAMMU_VERSION=1.44.0
ARG GAMMU_PR=1177

COPY requirements.txt /app/requirements.txt

# py3-cryptography and py3-openssl come from apk rather than pip: cryptography
# has no musl wheel for every architecture, and building it from source needs a
# Rust toolchain, which fails the i386 build. Alpine ships both prebuilt.
RUN apk update \
    && apk add --no-cache \
        python3 \
        py3-pip \
        py3-cryptography \
        py3-openssl \
        usb-modeswitch \
        usb-modeswitch-udev \
    && apk add --no-cache --virtual .build-deps \
        build-base \
        cmake \
        curl \
        git \
        patch \
        pkgconfig \
        python3-dev \
        libffi-dev \
        linux-headers \
    #
    # Tripwire. A merged PR means the fix is heading for a release and this
    # source build should be retired.
    && if curl -fsSL "https://api.github.com/repos/gammu/gammu/pulls/${GAMMU_PR}" \
            | tr -d ' ' | grep -q '"merged":true'; then \
         echo "ERROR: gammu#${GAMMU_PR} has been merged upstream."; \
         echo "Set GAMMU_VERSION to a release containing the fix and delete this patch step."; \
         exit 1; \
       fi \
    && git clone --quiet --depth 1 --branch "${GAMMU_VERSION}" \
        https://github.com/gammu/gammu.git /tmp/gammu-src \
    && curl -fsSL "https://github.com/gammu/gammu/pull/${GAMMU_PR}.diff" -o /tmp/gammu-pr.diff \
    # patch exits non-zero if the change is missing or already present, so a
    # gammu bump that includes the fix fails here rather than silently no-opping.
    && patch -p1 -d /tmp/gammu-src < /tmp/gammu-pr.diff \
    # Prefix /usr so libGammu lands on musl's default search path and gammu.pc is
    # where pkg-config looks when python-gammu is compiled below.
    && cmake -S /tmp/gammu-src -B /tmp/gammu-build \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_INSTALL_PREFIX=/usr \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DWITH_BLUETOOTH=OFF \
        -DWITH_IRDA=OFF \
        -DWITH_CURL=OFF \
        -DWITH_MySQL=OFF \
        -DWITH_Postgres=OFF \
        -DWITH_ODBC=OFF \
        -DWITH_PYTHON=OFF \
        -DBUILD_TESTING=OFF \
    && make -C /tmp/gammu-build -j2 \
    && make -C /tmp/gammu-build install \
    # --no-binary python-gammu is load bearing. PyPI ships musllinux wheels that
    # auditwheel has repaired, meaning they carry their own libGammu (plus
    # libssl, libcrypto, libmariadb, libpq, ...) inside python_gammu.libs/ with
    # the ELF references rewritten to point there. Installing that wheel makes
    # the extension ignore the patched library built above, and sending fails
    # with TIMEOUT[14]. Building from the sdist compiles against gammu-dev and
    # links /usr/lib/libGammu.so.8, and drops the bundled copies with it.
    && pip3 install --break-system-packages --no-cache-dir \
        --no-binary python-gammu -r /app/requirements.txt \
    && apk del .build-deps \
    && rm -rf /tmp/gammu-src /tmp/gammu-build /tmp/gammu-pr.diff /var/cache/apk/*

RUN python3 -c "import gammu; v = gammu.Version(); print('libGammu', v[0], 'python-gammu', v[1])"

WORKDIR /app

# Copy application files
COPY run.py .
COPY support.py .
COPY urc_filter.py .
COPY mqtt_publisher.py .
COPY config.json .
COPY run.sh .
COPY icon.png .
COPY services.yaml .

# Make run script executable
RUN chmod +x run.sh

# Expose port
EXPOSE 5000

# Labels
LABEL \
    io.hass.name="SMS Gammu Gateway (HomeOps)" \
    io.hass.description="REST API SMS Gateway using python-gammu for USB GSM modems" \
    io.hass.type="addon" \
    maintainer="ocalvo"

# Run
CMD [ "./run.sh" ]
