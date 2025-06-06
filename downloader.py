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

def fetch_photos(flickr, tags, taken_date, user_id):
    """Fetch photos based on query parameters."""
    photos = flickr.photos.search(user_id=user_id, tags=tags, min_taken_date=taken_date, extras='url_o')
    return photos['photos']['photo']

def main():
    parser = argparse.ArgumentParser(description="Download photos from Flickr by query.")
    parser.add_argument("tags", help="Flickr tags.")
    parser.add_argument("taken_date", help="Taken date in YYYY-MM-DD format.")
    parser.add_argument("destination", help="Destination folder for downloaded images.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing images.")
    args = parser.parse_args()

    flickr = authenticate_flickr()
    ensure_destination_folder(args.destination)

    user_id = flickr.test.login()['user']['id']  # Default to the authenticated user
    photos = fetch_photos(flickr, args.tags, args.taken_date, user_id)

    for photo in photos:
        if 'url_o' in photo:
            filepath = os.path.join(args.destination, f"{photo['id']}.jpg")
            download_photo(photo['url_o'], filepath, args.overwrite)

if __name__ == "__main__":
    main()
