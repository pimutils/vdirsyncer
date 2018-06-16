# Original file copyright 2017 Jelmer Vernooij

FROM ubuntu:bionic
RUN apt-get update && apt-get -y install xandikos locales
EXPOSE 8080

RUN locale-gen en_US.UTF-8
ENV PYTHONIOENCODING=utf-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

CMD xandikos -d /tmp/dav -l 0.0.0.0 -p 5001 --autocreate
