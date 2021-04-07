#!/bin/sh

cd $(git rev-parse --show-toplevel)

docker build -t baikal docker/baikal
docker run -d -p 8002:80 baikal
