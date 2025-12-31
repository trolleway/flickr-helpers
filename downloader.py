import argparse
import os
import flickrapi
import requests
import config
from tqdm import tqdm
from dateutil import parser as dateutil_parser

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
       
    else:
        print(f"Failed to download {url}")

def fetch_photos(flickr, tags, taken_date, user_id, max_taken_date):
    """Fetch photos based on query parameters."""

    params = {}
    if tags is not None and tags.strip() !='':
        params["tags"]=tags 
    params["user_id"] = flickr.test.login()['user']['id']
    params['sort']='date-taken-asc'
    params['per_page']=500
    params['page'] = 1
    params['content_types']='0'
    params['min_taken_date']=taken_date
    params['max_taken_date']=max_taken_date
    params['extras'] = 'url_o,date_taken,tags'
    result_list = list()
    gonextpage=True
    page_counter=0
    while(gonextpage):
        page_counter = page_counter+1
        params['page']=page_counter
        photos = flickr.photos.search(**params)

        msg=str(photos['photos']['page']).zfill(2) + ' / '+str(photos['photos']['pages']).zfill(2)
        print(msg)
        result_list_page=photos["photos"]["photo"]
        result_list=result_list+result_list_page
        gonextpage=False
        if len(result_list_page)>0 and photos['photos']['pages']>page_counter:
            gonextpage=True
    return     result_list
        
    
    
    return photos['photos']['photo']

def generate_editorial_caption(city, country, dt, description, suffix):
    """
    Generate a Shutterstock editorial caption.
    
    Args:
        city (str): City where the photo was taken.
        country (str): Country where the photo was taken.
        dt (datetime): 
        description (str): Description of the scene (factual, present tense).
        photographer (str): Your name for credit line.
    
    Returns:
        str: Formatted editorial caption.
    """
    # Parse date and format as "Month Day, Year"

    formatted_date = dt.strftime("%B %d, %Y")
    
    # Build caption
    caption = f"{city}, {country} - {formatted_date} - {description}{suffix}"
    return caption
    
def main():
    parser = argparse.ArgumentParser(description="Download photos from Flickr by tag taken at one day")
    parser.add_argument("tags", help="Flickr tags.")
    parser.add_argument("taken_date", help="Taken date in YYYY-MM-DD format.")
    parser.add_argument("destination", help="Destination folder for downloaded images.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing images.")
    parser.add_argument("--preset", choices=["wikicommons", "shutterstock"],default="wikicommons",required=True,help="wikicommons: write prefix, srcid. shutterstock: write date")
    parser.add_argument("--city",default="Moscow",help="city for Shutterstock caption")
    parser.add_argument("--country",default="Russia",help="city for Shutterstock caption")
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
    total=len(photos)
    i=0
    for photo in tqdm(photos):
        i=i+1
        if 'url_o' in photo:
            if args.preset == 'wikicommons':
                tds=photo['datetaken'].replace(':','')
                suffix=str(i).zfill(2)
                title=photo['title']
                if '/' in title:
                    title=title[:title.find('/')]
                name = f"{title[0:40]}_{tds}_flickr{photo['id']}__suffix{suffix}"+os.path.splitext(photo['url_o'])[-1] 
                name = name.replace(' ','_')
            elif args.preset == 'shutterstock':
                try:

                    datetaken = dateutil_parser.parse(photo['datetaken'], fuzzy=True)
                    
                    if not all(hasattr(datetaken, attr) for attr in ['year', 'month', 'day']):
                        datetaken = None
                except Exception:
                    datetaken = None
                caption = generate_editorial_caption(
                city=args.city,
                country=args.country,
                dt=datetaken,
                description=photo['title'],
                suffix=str(i).zfill(2)
                )
                name = caption+os.path.splitext(photo['url_o'])[-1] 
                

            filepath = os.path.join(args.destination, name)
            
            if 'posted' in photo['tags']:
                print('tagged as posted, skip '+photo['url_o']+ 'try to remove if already downloaded')
                if os.path.isfile(filepath): os.remove(filepath)
                continue
            download_photo(photo['url_o'], filepath, args.overwrite)

if __name__ == "__main__":
    main()
