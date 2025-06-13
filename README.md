# flickr-helpers

Scripts for download and manage flickr photos

## Run in Docker

```
docker build --tag flickr-helpers:dev .
docker run --rm -v "${PWD}:/opt/flickr-helpers" -it flickr-helpers:dev 
```

## Run in Termux

```
pip install -r requirements.txt
```

## login

1. Register a flickr application, obtain a api key and api secret
2.
```
cp config.example.py config.py
```
3. edit config.py


## Download your content from Flickr to social netrorks

Download a images/videos taken at given day with tags to folder.
```
python downloader.py "nature" "2025-06-13" "/downloads" --overwrite
```

### Filter already uploaded images

Download script will pass images with strin 'uploaded' in tags, and delete these from disk, if it already downloaded.
So when you post some photos, add tag 'uploadedSocial' to flickr, run downloader for second time, and local folder will be clear