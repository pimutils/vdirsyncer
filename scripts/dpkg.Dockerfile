ARG distro
ARG distrover

FROM $distro:$distrover

ARG distro
ARG distrover

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN if [ "$distrover" = "trusty" ]; then \
        add-apt-repository -y ppa:spotify-jyrki/dh-virtualenv; \
    fi
RUN if [ "$distro" = "debian" ]; then \
        echo "deb http://deb.debian.org/debian ${distrover}-backports main" > /etc/apt/sources.list.d/backports.list; \
    fi
RUN apt-get update
RUN apt-get install -y build-essential fakeroot debhelper git
RUN apt-get install -y python3-all python3-pip

RUN apt-get install -t${distrover}-backports -y dh-virtualenv

RUN pip3 install virtualenv
RUN python3 -m virtualenv /vdirsyncer/env/

COPY . /vdirsyncer/vdirsyncer/
WORKDIR /vdirsyncer/vdirsyncer/

RUN . /vdirsyncer/env/bin/activate; make install-dev
RUN /vdirsyncer/env/bin/python scripts/write-dpkg-changelog.py > debian/changelog
RUN . /vdirsyncer/env/bin/activate; dpkg-buildpackage -us -uc
RUN mkdir /vdirsyncer/pkgs/
RUN mv /vdirsyncer/*.deb /vdirsyncer/pkgs/
