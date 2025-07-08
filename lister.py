#!/usr/bin/env python3

import argparse
import sys
import flickrapi
import config
from datetime import datetime, timedelta


# Set up argument parser
parser = argparse.ArgumentParser(description="Search photos on Flickr with optional parameters.")
parser.add_argument("--user_id", type=str, help="Flickr user ID, by default it you", required=False)
parser.add_argument("--tags", type=str, help="Comma-separated tags for search", required=False)
parser.add_argument("--tag_mode", type=str, choices=["all", "any"], help="Tag mode: 'all' or 'any'", required=False)
parser.add_argument("--min_taken_date", type=str, help="Minimum taken date (YYYY-MM-DD format)", required='--max_taken_date' in sys.argv or '--interval' in sys.argv)


parser.add_argument("--query", type=str, choices=["search", "getWithoutGeoData"], default='search', help="query on flickr api", required=False)

duration = parser.add_mutually_exclusive_group(required=False)
duration.add_argument("--max_taken_date", type=str, help="Maximum taken date (YYYY-MM-DD format)", required=False)
duration.add_argument("--interval", type=str,  choices=["day"], required=False)

parser.add_argument("--output", type=str, choices=["json", "html"],default='json',required=False)

epilog='''lister.py --min_taken_date 2017-03-26 --max_taken_date 2017-03-27'''

args = parser.parse_args()


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

flickr = authenticate_flickr()

# Prepare parameters dynamically
search_params = {}
if args.user_id:
    search_params["user_id"] = args.user_id
else:
    search_params["user_id"]=flickr.test.login()['user']['id']
if args.tags:
    search_params["tags"] = args.tags
if args.tag_mode:
    search_params["tag_mode"] = args.tag_mode
if args.min_taken_date:
    search_params["min_taken_date"] = args.min_taken_date
if args.interval == 'day':
    search_params["max_taken_date"] = (datetime.strptime(args.min_taken_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
if args.max_taken_date:
    search_params["max_taken_date"] = args.max_taken_date

search_params["extras"] = 'url_s,url_o,date_taken,tags,geo'


# Execute search with only provided parameters
if args.query == 'search':
    photos = flickr.photos.search(**search_params)
elif args.query == 'getWithoutGeoData':
    photos = flickr.photos.getWithoutGeoData(**search_params)

# Print results
if args.output == 'json':
    import json
    print(json.dumps(photos))
elif args.output == 'html':
    
    html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flickr Photo Data</title>
    <style>
{css}
    </style>
</head><body><table>{rows}</table><h2>organizr</h2>
{links}
</body></html>'''
    css='''        body {
            background-color: #1a1a1a;
            color: #ffffff;
            font-family: Arial, sans-serif;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #444;
            padding: 4px;
            text-align: left;
        }
        th {
            background-color: #333;
        }
        a {
            color: #ffcc00;
        }
        
        td.monospace {font-family: monospace;}

        
        img {
    transition: transform 0.5s ease-in-out;
}

img:hover {
    transform: scale(1.1);
}

/* fade in */
table {
    opacity: 0;
    animation: fadeIn 1s ease-in forwards;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

        
        '''
    
    rows=''
    no_geo_pics_ids=list()
    
    photosbydate = sorted(photos['photos']['photo'], key=lambda x: x["datetaken"], reverse=True)
    
    for pic in photosbydate:
        geo_text=''
        if pic['latitude']==0: 
            geo_text='🌍❌'
            no_geo_pics_ids.append(pic['id'])
        row=f'''<tr><td>{pic['datetaken']}</td><td><a href="https://www.flickr.com/photos/{pic['owner']}/{pic['id']}"><img src="{pic['url_s']}"></a><td>{pic['title']}</td><td class="monospace">{pic['tags']}</td><td>{geo_text}</td>\n'''
        
        rows = rows + row
    
    ids_all=list()
    for pic in photosbydate:
        ids_all.append(pic['id'])
    links=''
    links += '''<a href="https://www.flickr.com/photos/organize/?ids='''+','.join(ids_all)+'''">open in organizr all pics from page</a></br>'''
    links += '''<a href="https://www.flickr.com/photos/organize/?ids='''+','.join(no_geo_pics_ids)+'''">open in organizr images without coordinates</a></br>'''
    html_template = html_template.format(css=css,rows=rows, links=links)
    print(html_template)