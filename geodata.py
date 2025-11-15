#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import flickrapi
import config
from datetime import datetime, timedelta
import re
import ndjson
from tqdm import tqdm
import time

# Set up argument parser
parser = argparse.ArgumentParser(description="Create or update NGGEOJSON file of flickr file coordinstes")
parser.add_argument("-o",help="output file")
parser.add_argument("--user_id", type=str, help="Flickr user ID, by default it you", required=False)
parser.add_argument("--min_taken_date", type=str, help="Minimum taken date (YYYY-MM-DD format)", required='--max_taken_date' in sys.argv or '--interval' in sys.argv)
parser.add_argument("--username", type=str, help="flickr username", required=False)

duration = parser.add_mutually_exclusive_group(required=False)
duration.add_argument("--max_taken_date", type=str, help="Maximum taken date (YYYY-MM-DD format)", required=False)
duration.add_argument("--interval", type=str,  choices=["day"], required=False)


epilog='''.py --min_taken_date 2017-03-26 --max_taken_date 2017-03-27 '''

args = parser.parse_args()


import os
from datetime import datetime

from typing import List, Dict
from dateutil import parser

from datetime import datetime, timedelta

def get_dates_between(start_date_str, end_date_str,step=1):
    # Convert strings to datetime objects
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    # Ensure start_date <= end_date
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    # Generate list of dates
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=step)
    
    return date_list

def record_pack2geojson(photo,userid=''):
    record = {"type":"Feature"}
    record['properties']=dict()
    for key in photo:
        record['properties'][key] = photo[key]
    record['properties']['url'] = f"https://flickr.com/photos/{photo['owner']}/{photo['id']}"
    record['geometry']={"type":"Point","coordinates":[float(photo['longitude']),float(photo['latitude'])]}
    
    return record
    
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

DAYS_PER_QUERY=2

# Prepare parameters dynamically
search_params = {}
if args.user_id:
    search_params["user_id"] = args.user_id
else:
    search_params["user_id"]=flickr.test.login()['user']['id']

if args.min_taken_date:
    search_params["min_taken_date"] = args.min_taken_date
if args.interval == 'day':
    search_params["max_taken_date"] = (datetime.strptime(args.min_taken_date, "%Y-%m-%d") + timedelta(days=DAYS_PER_QUERY)).strftime("%Y-%m-%d")
if args.max_taken_date:
    search_params["max_taken_date"] = args.max_taken_date
    

if args.max_taken_date:
    dates=get_dates_between(search_params["min_taken_date"], search_params["max_taken_date"],DAYS_PER_QUERY)
else:
    dates=[]
    dates.append(search_params["min_taken_date"])
    
for date2search in tqdm(dates):  
  
    search_params["min_taken_date"] = date2search
    search_params["max_taken_date"] = (datetime.strptime(date2search, "%Y-%m-%d") + timedelta(days=DAYS_PER_QUERY)).strftime("%Y-%m-%d")
    search_params['sort']='date-taken-asc'
    search_params['per_page']=500
    search_params['has_geo']=1
    search_params['privacy_filter']=1

    search_params["extras"] = 'url_s,url_o,url_l,url_k,date_taken,tags,geo'
    result_list = list()
    gonextpage=True
    page_counter=0
    
    # First request to know total pages
    tqdm.write(search_params["min_taken_date"]+'..'+search_params["max_taken_date"])
    photos = flickr.photos.search(**search_params)
    total_pages = photos['photos']['pages']
    with tqdm(total=total_pages, desc=f"Pages for {date2search}", leave=False) as pbar:
        while gonextpage:
            page_counter = page_counter+1
            search_params['page']=page_counter
            photos = flickr.photos.search(**search_params)

            result_list_page=photos["photos"]["photo"]
            result_list=result_list+result_list_page
            gonextpage=False
            
            pbar.update(1)  # update progress bar
            if len(result_list_page)>0 and photos['photos']['pages']>page_counter:
                gonextpage=True

        photos = result_list
        del result_list


    photosbydate = sorted(photos, key=lambda x: x["datetaken"], reverse=False)



    filename=args.o
    if args.username:
        username = args.username
    else:
        username = flickr.test.login()['user']['id']
        
    if os.path.isfile(filename) and os.path.exists(filename):
        # Reading
        with open(filename) as f:
            loaded_list = ndjson.load(f)   # returns a list of dicts
            photos_dict = dict()
            for s in loaded_list:
                photos_dict[s['properties']['id']]=s
            
            for photo in photosbydate:
                if photo['id'] in photos_dict:
                    photos_dict[photo['id']]=record_pack2geojson(photo,userid=username)
                else:
                    photos_dict[photo['id']]=record_pack2geojson(photo,userid=username)

            
        with open(filename, "w") as f:
            writer = ndjson.writer(f)
            for key in photos_dict:
                writer.writerow(photos_dict[key])
                
                
    else:
        # write fresh file
        with open(filename, "w") as f:
            writer = ndjson.writer(f)
            for photo in photosbydate:
                record=record_pack2geojson(photo,userid=username)
                writer.writerow(record)
    
    time.sleep(1)

