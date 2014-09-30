FROM python:3.4

MAINTAINER Byron Ruth <b@devel.io>

# Install dependencies
RUN apt-get -qq update
RUN apt-get -qq install -y python3 python3-pip

ADD . /data

WORKDIR /data

RUN pip3 install -q .

ENTRYPOINT ["htq", "--host", "0.0.0.0", "--redis", "redis"]
