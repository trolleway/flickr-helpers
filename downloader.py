import argparse
import os
import flickrapi
import requests
import config

def authenticate_flickr():
    """Authenticate and return the Flickr API client in a Termux-friendly way."""
    flickr = flickrapi.FlickrAPI(config.API_KEY, config.API_SECRET, format='parsed-json')
    
    if not flickr.token_cache.token:
        flickr.get_request_token(oauth_callback='oob')
        authorize_url = flickr.auth_url(perms='read')
        print(f"Go to this URL: {authorize_url}")
        verifier = input("Enter the verifier code from the website: ")
        flickr.get_access_token(verifier)
    
    return flickr


def ensure_destination_folder(folder):
    """Ensure the destination folder exists."""
    if not os.path.exists(folder):
        print(f'creating {folder}')
        os.makedirs(folder)

def download_photo(url, filepath, overwrite):
    """Download photo if necessary."""
    if os.path.exists(filepath):
        if overwrite:
            print(f"Overwriting {filepath}")
        else:
            print(f"Skipping {filepath}, already exists")
            return

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filepath, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        print(f"Downloaded {filepath}")
    else:
        print(f"Failed to download {url}")

def fetch_photos(flickr, tags, taken_date, user_id, max_taken_date):
    """Fetch photos based on query parameters."""
    print(taken_date, max_taken_date)
    page=1
    assert page>0
    photos = flickr.photos.search(user_id=user_id, tags=tags,
 min_taken_date=taken_date, 
max_taken_date=max_taken_date,
extras='url_o,date_taken')
    return photos['photos']['photo']

def main():
    parser = argparse.ArgumentParser(description="Download photos from Flickr by tag taken at one day")
    parser.add_argument("tags", help="Flickr tags.")
    parser.add_argument("taken_date", help="Taken date in YYYY-MM-DD format.")
    parser.add_argument("destination", help="Destination folder for downloaded images.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing images.")
    args = parser.parse_args()

    flickr = authenticate_flickr()
    ensure_destination_folder(args.destination)

    assert '-' in args.taken_date

    user_id = flickr.test.login()['user']['id']  # Default to the authenticated user
    from datetime import datetime, timedelta
    taken_date = args.taken_date
    max_taken_date = (datetime.strptime(taken_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    photos = fetch_photos(flickr, args.tags, taken_date, user_id, max_taken_date)
    if len(photos)>0:
         print(f'total is {len(photos)}')
    print(photos)
    for photo in photos:
        if 'url_o' in photo:
            tds=photo['datetaken'].replace(':','')
            filepath = os.path.join(args.destination, f"{tds} {photo['id']}.jpg")
            download_photo(photo['url_o'], filepath, args.overwrite)

if __name__ == "__main__":
    main()
