import argparse
import os
import flickrapi
import requests
import config
from tqdm import tqdm

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
    '''
    print(taken_date, max_taken_date)
    page=1
    assert page>0
    photos = flickr.photos.search(user_id=user_id, tags=tags,
tag_mode='all',
 min_taken_date=taken_date, 
max_taken_date=max_taken_date,
per_page=500,
extras='url_o,date_taken,tags')
    '''
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
    total=len(photos)
    i=0
    for photo in tqdm(photos):
        i=i+1
        if 'url_o' in photo:
            tds=photo['datetaken'].replace(':','')
            suffix=str(i).zfill(2)
            name = f"{tds}_flickr{photo['id']}_{photo['title'].replace('/','')[0:40]}_suffix{suffix}"+os.path.splitext(photo['url_o'])[-1] 
            name = name.replace(' ','_')
            filepath = os.path.join(args.destination, name)
            
            if 'posted' in photo['tags']:
                print('tagged as posted, skip '+photo['url_o']+ 'try to remove if already downloaded')
                if os.path.isfile(filepath): os.remove(filepath)
                continue
            download_photo(photo['url_o'], filepath, args.overwrite)

if __name__ == "__main__":
    main()
