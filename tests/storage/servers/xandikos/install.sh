#!/bin/sh

cd $(git rev-parse --show-toplevel)

docker build -t xandikos docker/xandikos
docker run -d -p 8000:8000 xandikos
