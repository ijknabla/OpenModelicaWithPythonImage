ARG PY_VERSION
ARG DEBIAN_CODENAME

FROM python:${PY_VERSION}-${DEBIAN_CODENAME}

ARG OMC_VERSION
ARG DEBIAN_CODENAME

LABEL maintainer "ijknabla <ijknabla@gmail.com>"

RUN useradd -m user

RUN apt-get update \
    && apt-get upgrade -qy \
    && apt-get dist-upgrade -qy \
    && apt-get install -qy sudo gnupg wget ca-certificates apt-transport-https \
    && echo "deb https://build.openmodelica.org/omc/builds/linux/releases/${OMC_VERSION}/ ${DEBIAN_CODENAME} release" > /etc/apt/sources.list.d/openmodelica.list \
    && wget https://build.openmodelica.org/apt/openmodelica.asc -O- | apt-key add - \
    && apt-get update \
    && apt-get upgrade \
    && apt-get dist-upgrade \
    && apt-get install --no-install-recommends -qy omc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
