ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:3.19
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# libGammu is built from source rather than installed from apk so it carries the
# SMS prompt fix. Alpine's gammu only recognises an SMS prompt of "> ", which
# stalls GSM_SendSMS on modems emitting a bare ">" (eg. SIMCom SIM7670G).
#
# That fix is no longer a patch. It was merged upstream on 2026-08-09 as
# gammu/gammu#1177, so this pins the merge commit instead of applying a diff --
# one source of truth, and no risk of a patch that silently stops applying.
#
# No release contains it yet: 1.44.0 shipped 2026-08-04, before the merge. The
# guard below fails the build as soon as gammu cuts any newer release, since any
# release after the merge date carries the fix, at which point this should move
# to a plain release tag and drop the pinned commit.
#
# Whatever it is pinned to must satisfy GAMMU_REQUIRED in python-gammu's
# setup.py, which is 1.44.0 as of python-gammu 3.4.0. Building the sdist against
# anything older fails with "Can not find supported Gammu version using
# pkg-config!". The pinned commit is master after 1.44.0, so it qualifies.
ARG GAMMU_COMMIT=c251dcce795d68cf358420111d00853d45169138
ARG GAMMU_LAST_RELEASE=1.44.0

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
        pkgconfig \
        python3-dev \
        libffi-dev \
        linux-headers \
    #
    # Tripwire. Any gammu release cut after 2026-08-09 contains the SMS prompt
    # fix, so the first one to appear should replace this pinned commit. Left
    # deliberately noisy: building master forever is not the intended end state.
    # A failed lookup (rate limit, no network) yields an empty string and is
    # skipped rather than breaking the build for an unrelated reason.
    && LATEST_RELEASE="$(curl -fsSL https://api.github.com/repos/gammu/gammu/releases/latest \
            | tr -d ' ' | sed -n 's/.*"tag_name":"\([^"]*\)".*/\1/p' || true)" \
    && if [ -n "${LATEST_RELEASE}" ] && [ "${LATEST_RELEASE}" != "${GAMMU_LAST_RELEASE}" ]; then \
         echo "ERROR: gammu ${LATEST_RELEASE} has been released."; \
         echo "It postdates the merge of the SMS prompt fix (gammu/gammu#1177)."; \
         echo "Build from that tag and delete GAMMU_COMMIT and this guard."; \
         exit 1; \
       fi \
    # A commit tarball rather than a clone: no git in the image, and the content
    # is pinned by hash rather than by a branch that moves.
    && curl -fsSL "https://github.com/gammu/gammu/archive/${GAMMU_COMMIT}.tar.gz" \
        -o /tmp/gammu.tar.gz \
    && mkdir -p /tmp/gammu-src \
    && tar -xzf /tmp/gammu.tar.gz -C /tmp/gammu-src --strip-components=1 \
    # Assert the pinned commit really carries the fix. Cheap, and it turns a
    # mistyped hash into a build failure rather than an image that cannot send.
    && grep -q 'AT_SMS_PROMPT_BARE' /tmp/gammu-src/libgammu/protocol/at/at.h \
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
    && rm -rf /tmp/gammu-src /tmp/gammu-build /tmp/gammu.tar.gz /var/cache/apk/*

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
