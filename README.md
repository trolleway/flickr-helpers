# flickr-helpers


docker build --tag flickr-helpers:dev .
docker run --rm -v "${PWD}:/opt/flickr-helpers" -it flickr-helpers:dev 