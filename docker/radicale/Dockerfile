FROM python:3.8

RUN pip install radicale

CMD radicale --storage-filesystem-folder /tmp/dav -H 0.0.0.0:8001 -D
