#!/usr/bin/env python3

import sys
import flickrapi
import config
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QScrollArea, QFrame, QMessageBox,QInputDialog, QTabWidget,QFormLayout,QGroupBox,QSizePolicy,QSpacerItem
    
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from datetime import datetime, timedelta

import argparse
import webbrowser
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtGui import QDesktopServices

from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, QUrl



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



class FlickrBrowser(QWidget):
    def __init__(self,args):
        super().__init__()
        self.setWindowTitle("Flickr Image Browser")
        self.args = args

        self.selecteds_list = list()


        self.init_ui()
        self.flickr = self.authenticate_flickr()
        
        self.css='''        body {
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

    def authenticate_flickr(self):
        flickr = flickrapi.FlickrAPI(config.API_KEY, config.API_SECRET, format='parsed-json')
        if not flickr.token_cache.token:
            flickr.get_request_token(oauth_callback='oob')
            auth_url = flickr.auth_url(perms='write')
            

            # inside authenticate_flickr() method
            webbrowser.open(auth_url)
            #QMessageBox.information(self, "Authorization", "Your browser has been opened to authorize this app.")

            verifier, ok = QInputDialog.getText(self, "Enter Verifier", "Paste the verifier code from the browser:")
            if not ok or not verifier:
                QMessageBox.warning(self, "Authorization Failed", "No verifier entered. Cannot proceed.")
                return
            flickr.get_access_token(verifier)
        return flickr
    
    def init_ui(self):
        layout = QVBoxLayout()

        # Input fields
        self.inputs_search = {}
        fields = ["tags", "tag_mode", "min_taken_date", "max_taken_date","days","per_page"]
        for field in fields:
            row = QHBoxLayout()
            label = QLabel(field)
            edit = QLineEdit()
            if hasattr(self.args, field) and getattr(self.args, field) is not None:
                edit.setText(str(getattr(self.args, field)))
            self.inputs_search[field] = edit
            row.addWidget(label)
            row.addWidget(edit)
            layout.addLayout(row)

        self.inputs_search["tag_mode"].setPlaceholderText("all or any")
        #self.inputs_search["per_page"].setText(str(50))
        self.inputs_search["days"].setInputMask("00") 
        #self.inputs_search["days"].setPlaceholderText("number")
        #self.inputs_search["page"].setPlaceholderText("1")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_photos)
        layout.addWidget(self.search_btn)
        
        self.browser_main_table = QWebEngineView()
        self.browser_main_table.setFixedHeight(450)
        layout.addWidget(self.browser_main_table)
        self.browser_main_table.setHtml('''<html><body><h1>wait for query</h1>''', QUrl("qrc:/"))
       
        
      
        
        self.setLayout(layout)



    def get_photos_with_timestamps(self,directory: str) -> List[Dict]:
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

    def simplify_photo_datetimes(self,photo_list: List[Dict]) -> List[Dict]:
        for photo in photo_list:
            dt = photo["datetime"]
            if dt.tzinfo:
                simplified = dt.replace(tzinfo=None)
            else:
                simplified = dt
            photo["simplified_datetime"] = simplified
        return photo_list

    def clip_localphotos_by_dates(self,photo_list: List[Dict],min_taken_date:str, max_taken_date:str) -> List[Dict]:

        start_date = datetime.strptime(min_taken_date, "%Y-%m-%d")
        end_date = datetime.strptime(max_taken_date, "%Y-%m-%d")
        new_list=list()
        for photo in photo_list:
            if start_date <= photo["simplified_datetime"] <= end_date:
                new_list.append(photo)
        return new_list

    def find_filckr_already_uploadeds(self,localphotos: List[Dict], flickrimgs: List[Dict]) -> List[Dict]:
        for photo in localphotos:
            dt = photo["simplified_datetime"]
            #print('search candidate for local photo '+str(dt))
            matched_flickrimgs=find_matching_flickrimgs(dt,flickrimgs)
            #print(matched_flickrimgs)
            photo["candidated_flickrimgs"] = matched_flickrimgs
            if len(matched_flickrimgs) == 0:
                photo["candidated_text"]='no match, do upload'
            
            if len(matched_flickrimgs) == 1:
                photo["candidated_text"]='1 found '
            
            if len(matched_flickrimgs) == 1 and 'namegenerated' in matched_flickrimgs[0].get('tags',''):
                photo["candidated_text"]='uploaded and named good on flickr, move local photo to uploaded folder'    
        return localphotos

    from datetime import datetime
    from dateutil import parser

    def find_matching_flickrimgs(self,dt: datetime, flickrimgs: list) -> list:
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


    def authenticate_flickr(self):
        """Authenticate and return the Flickr API client in a Termux-friendly way."""
        flickr = flickrapi.FlickrAPI(config.API_KEY, config.API_SECRET, format='parsed-json')
        
        if not flickr.token_cache.token:
            flickr.get_request_token(oauth_callback='oob')
            authorize_url = flickr.auth_url(perms='read')
            print(f"Go to this URL: {authorize_url}")
            verifier = input("Enter the verifier code from the website: ")
            flickr.get_access_token(verifier)
        
        return flickr

    def reset_search_results(self):
        self.browser_main_table.setHtml('''<html><body><h1>wait for query execute</h1>''', QUrl("qrc:/"))
        pass
    
    def search_photos(self):
        self.reset_search_results()
        params = {"extras": "url_w,date_taken,tags,geo"}
        for key, widget in self.inputs_search.items():
            val = widget.text().strip()
            if val:
                params[key] = val
        
        tags4query=params.get('tags','')
        params.pop("tags", None)

        # Add logic for "interval" (if max not given)
        if "min_taken_date" in params and "max_taken_date" not in params:
            try:
                raw_date = params["min_taken_date"]
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        date = datetime.strptime(raw_date, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError("Invalid date format")

                if 'days' in params:
                    next_day = date + timedelta(days=int(params['days']))
                    params["max_taken_date"] = next_day.strftime("%Y-%m-%d %H:%M:%S")

            except ValueError:
                QMessageBox.warning(self, "Invalid Date", "Use format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS")
                return



        params["user_id"] = self.flickr.test.login()['user']['id']
        params['sort']='date-taken-asc'
        params['per_page']=int(params.get('per_page') or 400)
        #params['page'] = 1
        params['content_types']='0'

        #params['page']=1
        photos = self.flickr.photos.search(**params)



        localphotos = self.get_photos_with_timestamps(args.localdir)
        localphotos = self.simplify_photo_datetimes(localphotos)
        localphotos = self.clip_localphotos_by_dates(localphotos,params["min_taken_date"],params["max_taken_date"])

        photosbydate = sorted(photos['photos']['photo'], key=lambda x: x["datetaken"], reverse=False)
        localphotos = self.find_filckr_already_uploadeds(localphotos,photosbydate)

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

            
            rows=''
            no_geo_pics_ids=list()
            
            localphotosbydate = sorted(localphotos, key=lambda x: x["simplified_datetime"], reverse=False)
            
            for pic in localphotosbydate:
                row=f'''<tr><td><img src="{pic['filepath']}" class="localphoto"></td>
                <td>{pic['filename']}</td>
                <td>{pic['simplified_datetime']}</td>
                <td>{pic.get('candidated_flickrimgs','')}</td>
                <td>{pic.get('candidated_text','')}</td>
                \n'''
                
                rows = rows + row   
            links='links'
            html_template = html_template.format(css=self.css,rows=rows, links=links)
            print(html_template) 
        

if __name__ == "__main__":
    
    

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Helper for process mass upload old photos to flickr and delete preious same uploaded photos, when old photos has less geodata. Output is html file with table.")
    parser.add_argument("localdir",help="local directory with photos")
    parser.add_argument("--user_id", type=str, help="Flickr user ID, by default it you", required=False)
    parser.add_argument("--tags", type=str, help="Comma-separated tags for search", required=False)
    parser.add_argument("--tag_mode", type=str, choices=["all", "any"], help="Tag mode: 'all' or 'any'", required=False)
    parser.add_argument("--min_taken_date", type=str, help="Minimum taken date (YYYY-MM-DD format)", required='--max_taken_date' in sys.argv or '--interval' in sys.argv)
    parser.add_argument('-re','--name-regexp')
    parser.add_argument("--per_page", type=int, help="per page param for flickr search api", required=False)

    parser.add_argument("--query", type=str, choices=["search", "getWithoutGeoData"], default='search', help="query on flickr api", required=False)

    duration = parser.add_mutually_exclusive_group(required=False)
    duration.add_argument("--max_taken_date", type=str, help="Maximum taken date (YYYY-MM-DD format)", required=False)
    duration.add_argument("--interval", type=str,  choices=["day"], required=False)


    epilog='''.py --min_taken_date 2017-03-26 --max_taken_date 2017-03-27 '''

    args = parser.parse_args()


    app = QApplication(sys.argv)
    window = FlickrBrowser(args)
    window.show()
    sys.exit(app.exec())

