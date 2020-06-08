ARG distro
ARG distrover

FROM $distro:$distrover

ARG distro
ARG distrover

RUN apt-get update
RUN apt-get install -y build-essential fakeroot debhelper git
RUN apt-get install -y python3-all python3-pip
RUN apt-get install -y ruby ruby-dev
RUN apt-get install -y python-all python-pip

RUN gem install fpm

RUN pip2 install virtualenv-tools
RUN pip3 install virtualenv
RUN virtualenv -p python3 /vdirsyncer/env/

COPY . /vdirsyncer/vdirsyncer/
WORKDIR /vdirsyncer/vdirsyncer/
RUN mkdir /vdirsyncer/pkgs/

RUN basename *.tar.gz .tar.gz | cut -d'-' -f2 | sed -e 's/\.dev/~/g' | tee version
RUN (echo -n *.tar.gz; echo '[google]') | tee requirements.txt
RUN . /vdirsyncer/env/bin/activate; fpm -s virtualenv -t deb \
-n "vdirsyncer-latest" \
-v "$(cat version)" \
--prefix /opt/venvs/vdirsyncer-latest \
requirements.txt

RUN mv /vdirsyncer/vdirsyncer/*.deb /vdirsyncer/pkgs/

WORKDIR /vdirsyncer/pkgs/
RUN dpkg -i *.deb
RUN LC_ALL=C.UTF-8 LANG=C.UTF-8 /opt/venvs/vdirsyncer-latest/bin/vdirsyncer --version
