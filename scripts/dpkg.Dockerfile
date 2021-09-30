ARG distro
ARG distrover

FROM $distro:$distrover

RUN apt-get update
RUN apt-get install -y build-essential fakeroot debhelper git
RUN apt-get install -y python3-all python3-pip python3-venv
RUN apt-get install -y ruby ruby-dev

RUN gem install fpm package_cloud

RUN pip3 install virtualenv virtualenv-tools3
RUN virtualenv -p python3 /vdirsyncer/env/

# See https://github.com/jordansissel/fpm/issues/1106#issuecomment-461678970
RUN pip3 uninstall -y virtualenv
RUN echo 'python3 -m venv "$@"' > /usr/local/bin/virtualenv
RUN chmod +x /usr/local/bin/virtualenv

COPY . /vdirsyncer/vdirsyncer/
WORKDIR /vdirsyncer/vdirsyncer/
RUN mkdir /vdirsyncer/pkgs/

RUN basename *.tar.gz .tar.gz | cut -d'-' -f2 | sed -e 's/\.dev/~/g' | tee version
RUN (echo -n *.tar.gz; echo '[google]') | tee requirements.txt
RUN fpm --verbose \
  --input-type virtualenv \
  --output-type deb \
  --name "vdirsyncer-latest" \
  --version "$(cat version)" \
  --prefix /opt/venvs/vdirsyncer-latest \
  --depends python3 \
  requirements.txt

RUN mv /vdirsyncer/vdirsyncer/*.deb /vdirsyncer/pkgs/

WORKDIR /vdirsyncer/pkgs/
RUN dpkg -i *.deb

# Check that it works:
RUN LC_ALL=C.UTF-8 LANG=C.UTF-8 /opt/venvs/vdirsyncer-latest/bin/vdirsyncer --version
