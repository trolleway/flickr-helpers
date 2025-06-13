FROM ubuntu:focal
ARG DEBIAN_FRONTEND=noninteractive
ARG APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=DontWarn


RUN apt-get update -y && apt-get upgrade -y



RUN 	apt-get -y install  --yes language-pack-ru software-properties-common \
	apt-transport-https ca-certificates curl gnupg 
#RUN	apt-add-repository ppa:nextgis/ppa && \
#	apt-get update -y && \
#	apt-get -y install --no-install-recommends --yes python3 python3-pip python3-psycopg2 gdal-bin python3-gdal python3-setuptools && \
#	update-locale LANG=ru_RU.UTF-8 && \
#	pip3 install --upgrade pip

RUN apt-get -y install --no-install-recommends --yes language-pack-ru apt-transport-https ca-certificates curl python3 python3-pip python3-psycopg2 
#RUN apt-get -y install ffmpeg mc dos2unix git




ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LC_ALL ru_RU.UTF-8
WORKDIR /opt/flickr-helpers
COPY requirements.txt requirements.txt
RUN pip3 install   -r requirements.txt 



CMD ["/bin/bash"]



