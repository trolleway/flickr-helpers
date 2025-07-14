#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import flickrapi
import config
from datetime import datetime, timedelta
import re


# Set up argument parser
parser = argparse.ArgumentParser(description="Helper for process mass upload old photos to flickr and delete preious same uploaded photos, when old photos has less geodata. Output is html file with table.")
parser.add_argument("localdir",help="local directory with photos")
parser.add_argument("--user_id", type=str, help="Flickr user ID, by default it you", required=False)
parser.add_argument("--tags", type=str, help="Comma-separated tags for search", required=False)
parser.add_argument("--tag_mode", type=str, choices=["all", "any"], help="Tag mode: 'all' or 'any'", required=False)
parser.add_argument("--min_taken_date", type=str, help="Minimum taken date (YYYY-MM-DD format)", required='--max_taken_date' in sys.argv or '--interval' in sys.argv)
parser.add_argument('-re','--name-regexp')

parser.add_argument("--query", type=str, choices=["search", "getWithoutGeoData"], default='search', help="query on flickr api", required=False)

duration = parser.add_mutually_exclusive_group(required=False)
duration.add_argument("--max_taken_date", type=str, help="Maximum taken date (YYYY-MM-DD format)", required=False)
duration.add_argument("--interval", type=str,  choices=["day"], required=False)


epilog='''.py --min_taken_date 2017-03-26 --max_taken_date 2017-03-27 '''

args = parser.parse_args()

'''
requireets
Pillow>=9.0.0
python-dateutil>=2.8.0
'''
import os
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
from typing import List, Dict
from dateutil import parser

def get_local_photos_dates_list(photo_list: List[Dict]) -> List[Dict]:
    dates = list()
    for photo in photo_list:
        d=photo.get('simplified_datetime')
        if d not in dates:
            dates.append(d)
    return dates

def get_photos_with_timestamps(directory: str) -> List[Dict]:
    results = []
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath) and filename.lower().endswith(".jpg"):
            try:
                img = Image.open(filepath)
                exif_data = img._getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == 'DateTimeOriginal':
                            dt = parser.parse(value.replace(":", "-", 2))
                            results.append({
                                "filepath": filepath,
                                "filename": filename,
                                "datetime": dt
                            })
                            break
            except Exception as e:
                print(f"Failed to process {filename}: {e}")
    return results

def simplify_photo_datetimes(photo_list: List[Dict]) -> List[Dict]:
    for photo in photo_list:
        dt = photo["datetime"]
        if dt.tzinfo:
            simplified = dt.replace(tzinfo=None)
        else:
            simplified = dt
        photo["simplified_datetime"] = simplified
    return photo_list

def clip_localphotos_by_dates(photo_list: List[Dict],min_taken_date:str, max_taken_date:str) -> List[Dict]:

    start_date = datetime.strptime(min_taken_date, "%Y-%m-%d")
    end_date = datetime.strptime(max_taken_date, "%Y-%m-%d")
    new_list=list()
    for photo in photo_list:
        if start_date <= photo["simplified_datetime"] <= end_date:
            new_list.append(photo)
    return new_list

def find_filckr_already_uploadeds(localphotos: List[Dict], flickrimgs: List[Dict]) -> List[Dict]:

    flickr2del=list()
    for photo in localphotos:
        dt = photo["simplified_datetime"]
        #print('search candidate for local photo '+str(dt))
        matched_flickrimgs=find_matching_flickrimgs(dt,flickrimgs)
        #print(matched_flickrimgs)
        photo["candidated_flickrimgs"] = matched_flickrimgs
        flickr_geo = False
        if len(matched_flickrimgs) == 0:
            photo["candidated_text"]='no match, do upload'
        
        if len(matched_flickrimgs) == 1:
            photo["candidated_text"]='1 found '
            if matched_flickrimgs[0].get('longitude',0)!=0:
                flickr_geo = True
            
            if flickr_geo == True:
                photo["candidated_text"]='1 found '
            elif flickr_geo == False:
                editurl='''<a href="https://www.flickr.com/photos/organize/?ids='''+matched_flickrimgs[0].get('id')+'''">organizr</a></br>'''
                photo["candidated_text"] +='1 found flickr image has no geotag'
                photo["editurl"]=editurl
                flickr2del.append(matched_flickrimgs[0].get('id'))

        
        if len(matched_flickrimgs) == 1 and 'namegenerated' in matched_flickrimgs[0].get('tags',''):
            photo["candidated_text"]='uploaded and named good on flickr, move local photo to uploaded folder'    
    return localphotos,flickr2del

from datetime import datetime
from dateutil import parser

def find_matching_flickrimgs(dt: datetime, flickrimgs: list) -> list:
    matched = []
    # Remove microseconds for comparison (i.e., truncate to full seconds)
    dt_trimmed = dt.replace(microsecond=0)

    for flickrimg in flickrimgs:
        datetaken_str = flickrimg.get('datetaken', '')
        try:
            parsed_dt = parser.parse(datetaken_str)
            parsed_dt_trimmed = parsed_dt.replace(microsecond=0)

            if parsed_dt_trimmed.replace(tzinfo=None) == dt_trimmed:
                matched.append(flickrimg)
        except (ValueError, TypeError):
            continue
    return matched

def flickr_search_by_dateslist(search_params,local_photos_dates):
    
    #print(local_photos_dates)
    #print(search_params)
    flickrresult=dict()
    flickrresult['photos']=dict()
    flickrresult['photos']['photo']=list()
    
    days=list()
    for d in local_photos_dates:
        day = d.date()
        if day not in days:
            days.append(day)
    
    for day in days:
        search_params['min_taken_date']=day.strftime("%Y-%m-%d")
        search_params['max_taken_date']=(day + timedelta(days=1)).strftime("%Y-%m-%d")
        print(search_params)
        sr = flickr.photos.search(**search_params)
        srp=sr['photos']['photo']
        #print(flickrresult)
        flickrresult['photos']['photo'] += srp

    return flickrresult
    quit()

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



localphotos = get_photos_with_timestamps(args.localdir)
localphotos = simplify_photo_datetimes(localphotos)
local_photos_dates = get_local_photos_dates_list(localphotos)
if ('min_taken_date' in search_params and 'max_taken_date' in search_params):
    localphotos = clip_localphotos_by_dates(localphotos,search_params["min_taken_date"],search_params["max_taken_date"])
    photos = flickr.photos.search(**search_params)
else:
    print('process all dates')
    photos = flickr_search_by_dateslist(search_params,local_photos_dates)

photosbydate = sorted(photos['photos']['photo'], key=lambda x: x["datetaken"], reverse=False)
localphotos, flickr2del = find_filckr_already_uploadeds(localphotos,photosbydate)

# Execute search with only provided parameters


if 'html' == 'html':
    
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

.localphoto { width: 400px;}

        
        '''
    
    rows=''
    no_geo_pics_ids=list()
    
    localphotosbydate = sorted(localphotos, key=lambda x: x["simplified_datetime"], reverse=False)
    
    for pic in localphotosbydate:
        row=f'''<tr><td><img src="{pic['filepath']}" class="localphoto"></td>
        <td>{pic['filename']}</td>
        <td>{pic['simplified_datetime']}</td>
        <td>{pic.get('candidated_flickrimgs','')}</td>
        <td>{pic.get('candidated_text','')}</td>
        <td>{pic.get('editurl','')}</td>
        \n'''
        
        rows = rows + row  
    links=''
    if len(flickr2del)>0:
        links='''<a href="https://www.flickr.com/photos/organize/?ids='''+','.join(flickr2del)+'''">open in organizr pics for delete</a></br>'''
    
    html_template = html_template.format(css=css,rows=rows, links=links)
    print(html_template) 
   