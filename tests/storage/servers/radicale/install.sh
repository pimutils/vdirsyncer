#!/bin/sh

cd $(git rev-parse --show-toplevel)

docker build -t radicale docker/radicale
docker run -d -p 8001:8001 radicale
