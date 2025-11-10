import sys
import flickrapi
import config
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QScrollArea, QSplitter, QMessageBox,QInputDialog, QTabWidget,QFormLayout,QGroupBox,QSizePolicy,QSpacerItem, QFileDialog
    
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from datetime import datetime, timedelta
import webbrowser
import argparse
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtGui import QDesktopServices

from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, QUrl, Qt


import requests


from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

import pywikibot
import requests
from typing import Optional
import re
from transliterate import translit, get_available_language_codes
import os
from PIL import Image
from PIL.ExifTags import TAGS


class WikidataModel:
    """
    Simple Wikidata label fetcher using requests (unauthenticated).
    Caches results in memory to avoid redundant API calls.
    """
    def __init__(self):
        self.api_url = "https://www.wikidata.org/w/api.php"
        # cache keys are tuples (wdid, lang)
        self.cache = {"labels": {}}
        self.session = requests.Session()

    def get_name(self, wdid: str, lang: str = "en") -> Optional[str]:
        """
        Return the label for a given Wikidata Q-ID in the specified language.
        Returns None if the ID is invalid, the label is missing, or on error.
        """
        key = (wdid, lang)
        # 1) Check cache
        if key in self.cache["labels"]:
            return self.cache["labels"][key]

        # 2) Build request parameters
        params = {
            "action": "wbgetentities",
            "ids": wdid,
            "props": "labels",
            "languages": lang,
            "format": "json"
        }

        # 3) Perform HTTP GET and handle errors
        try:
            resp = self.session.get(self.api_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as http_err:
            print(f"[Error] HTTP error fetching {wdid}: {http_err}")
            return None
        except ValueError as parse_err:
            print(f"[Error] JSON parse error for {wdid}: {parse_err}")
            return None

        # 4) Extract label from JSON
        label = None
        entity = data.get("entities", {}).get(wdid, {})
        labels = entity.get("labels", {})
        if lang in labels:
            label = labels[lang].get("value",'')

        # 5) Cache & return
        self.cache["labels"][key] = label
        return label
    
    


class Backend(QObject):
    imgSelected = pyqtSignal(str)
    @pyqtSlot(str)
    def handle_select_img(self, image_id):
        try:
            self.imgSelected.emit(str(image_id))
        except:
            pass
        
    ShowImageOnMap = pyqtSignal(str)
    @pyqtSlot(str)
    def handle_ShowImageOnMap(self, image_id):
        try:
            self.ShowImageOnMap.emit(str(image_id))
        except:
            pass
        
    imgSelectedAppend = pyqtSignal(str)
    @pyqtSlot(str)
    def handle_select_img_append(self, image_id):
        self.imgSelectedAppend.emit(str(image_id))        

    imgMacros1 = pyqtSignal(str)
    @pyqtSlot(str)
    def handle_handleMacros1(self, image_id):
        self.imgMacros1.emit(str(image_id))  
    mapClick = pyqtSignal(float,float)     
    @pyqtSlot(float, float)
    def olimageClicked(self, lat, lon):
        self.mapClick.emit(float(lat),float(lon))

    # Signals used by the map JavaScript; add placeDestination so JS can connect to it
    placeMarker = pyqtSignal(float, float, str)
    placeDestination = pyqtSignal(float, float)
    clearMarkers = pyqtSignal()    

class ExternalLinkPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)
    
    
class Model():


    def more_tags_process(self,input_string):
        # Remove leading/trailing spaces
        trimmed = input_string.strip()

        # Check for empty or all-space input
        if not trimmed:
            return []

        # Check if input contains commas
        if ',' in trimmed:
            return [tag.strip() for tag in trimmed.split(',')]

        # Otherwise, return as a single-element list with stripped string
        return [trimmed]

    def address_image_flickr_update(self,flickr, photo_id, textsdict):

        # https://flickr.com/photos/trolleway/51052666337

        # Step 1: Get current photo info
        info = flickr.photos.getInfo(photo_id=photo_id)
        visibility = info['photo']['visibility']

        # Step 2: Check and update privacy if needed
        if visibility.get('ispublic') == 0:
            flickr.photos.setPerms(
                photo_id=photo_id,
                is_public=1,
                is_friend=0,
                is_family=0,
                perm_comment=3,  # Anyone can comment
                perm_addmeta=2   # Contacts can add tags/notes
            )
            print("Privacy changed to public.")

        # Step 3: Update photo metadata


       
        newname = str(textsdict.get('name',''))
        desc = str(textsdict.get('desc','')).strip()
        new_tags = str(textsdict.get('tags',''))
            
        if textsdict.get('more_tags','') != '':
            new_tags += ', '
            new_tags+=' '.join(self.more_tags_process(textsdict.get('more_tags','')))
        if new_tags[0]==',': new_tags=new_tags[1:]
            
        new_tags += ', namegenerated'

        flickr.photos.setMeta(
            photo_id=photo_id,
            title=newname,
            description = desc
        )

        # Step 4: Update tags
        flickr.photos.setTags(
            photo_id=photo_id,
            tags=new_tags
        )
    def street_image_flickr_update(self,flickr, photo_id, textsdict):

        # https://flickr.com/photos/trolleway/51052666337

        # Step 1: Get current photo info
        info = flickr.photos.getInfo(photo_id=photo_id)
        visibility = info['photo']['visibility']

        # Step 2: Check and update privacy if needed
        if visibility.get('ispublic') == 0:
            flickr.photos.setPerms(
                photo_id=photo_id,
                is_public=1,
                is_friend=0,
                is_family=0,
                perm_comment=3,  # Anyone can comment
                perm_addmeta=2   # Contacts can add tags/notes
            )
            print("Privacy changed to public.")

        # Step 3: Update photo metadata


       
        newname = str(textsdict.get('city','')) +' '+ str(textsdict.get('suburb_int','')) +' '+ str(textsdict.get('road_int',''))
        desc = str(textsdict.get('desc','')).strip() + ' '+ str(textsdict.get('road_loc',''))
        new_tags = str(textsdict.get('tags','')) + ', '+textsdict.get('city','')+', '+textsdict.get('suburb_int','')
            
        if textsdict.get('more_tags','') != '':
            new_tags += ', '
            new_tags+=' '.join(self.more_tags_process(textsdict.get('more_tags','')))
        if new_tags.strip() != '' and new_tags[0]==',': 
            new_tags=new_tags[1:]
            
        new_tags += ', namegenerated'

        flickr.photos.setMeta(
            photo_id=photo_id,
            title=newname,
            description = desc
        )

        # Step 4: Update tags
        flickr.photos.setTags(
            photo_id=photo_id,
            tags=new_tags
        )
        

    def transport_image_flickr_update(self,flickr, photo_id, textsdict):

        # https://flickr.com/photos/trolleway/51052666337

        # Step 1: Get current photo info
        info = flickr.photos.getInfo(photo_id=photo_id)
        visibility = info['photo']['visibility']

        # Step 2: Check and update privacy if needed
        if visibility.get('ispublic') == 0:
            flickr.photos.setPerms(
                photo_id=photo_id,
                is_public=1,
                is_friend=0,
                is_family=0,
                perm_comment=3,  # Anyone can comment
                perm_addmeta=2   # Contacts can add tags/notes
            )
            print("Privacy changed to public.")

        # Step 3: Update photo metadata

        city=textsdict.get('city','').capitalize()
        transport=textsdict["preset"].lower()
        number=str(textsdict.get('number'))
        datestr=info['photo']['dates']['taken'][0:10]
        street=textsdict.get("street",'')
        street_int=textsdict.get("street_int",'')
        street_loc=textsdict.get("street_loc",'')
        suburb_int=textsdict.get("suburb_int",'')
        model=textsdict.get('model')
        numberplate=textsdict.get('numberplate','').strip()
        route=str(textsdict.get('route'))
        operator = str(textsdict.get('operator','')).strip()
        region = str(textsdict.get('region','')).strip()
        desc = str(textsdict.get('desc','')).strip()
        if transport in ('bus','trolleybus','tram'):
            if number != '':
                simplenum = number
            elif numberplate is not None:
                simplenum = numberplate
            newname = f'{city} {transport} {simplenum} {datestr} {street} {model}'.replace('  ',' ')

            new_tags=f'"{city}" {transport} "{street}"'
            if route is not None and len(route)>0:
                new_tags += ' line'+str(route)
            if model is not None and len(model)>0:
                if ' ' in model:
                    new_tags += ' "'+str(model)+'"'
                else:    
                    new_tags += ' '+str(model)
            
            if operator != '':
                new_tags += ' "'+str(operator)+'"'
            if region != '':
                new_tags += ' "'+str(region)+'"' 
            
            if numberplate != '':
                new_tags += ' '+str(numberplate)
        
        elif transport == 'automobile':

            brand = str(textsdict.get('brand','')).strip()
            newname = f'{city} {brand} {model} {numberplate} {datestr} {street_int} '.replace('  ',' ')

            new_tags=f'"{city}" auto automobile "{street_int}"'
            if desc == '': desc = f' {brand} {model} {street_loc}'
            if model is not None and len(model)>0:
                if ' ' in model:
                    new_tags += ' "'+str(model)+'"'
                else:    
                    new_tags += ' '+str(model)
            if (model is not None and len(model)>0) and (brand is not None and len(brand)>0):
                new_tags += ' "'+str(brand)+'"'
                new_tags += ' "'+str(brand)+' ' +str(model) +'"'
            
            if operator != '':
                new_tags += ' "'+str(operator)+'"'
            if region != '':
                new_tags += ' "'+str(region)+'"' 
            
            if numberplate != '':
                new_tags += ' '+str(numberplate)  
        
        elif transport == 'trainstation':
            
            name = str(textsdict.get('name','')).strip()
            owner = str(textsdict.get('owner','')).strip()
            newname = f'{owner} station {name} {datestr}'.replace('  ',' ')
            desc = f'{owner} station {name}'

            new_tags=f'"{city}" "{owner}" "{name}" "station"'
            
            #for tag in [model, operator, station, line, region]:
            #    if tag:
            #        new_tags += f' "{tag}"'
                    
        elif transport == 'train':
            owner = str(textsdict.get('owner','')).strip()
            physical = str(textsdict.get('physical','')).strip()
            line = str(textsdict.get('line','')).strip()
            station = str(textsdict.get('station','')).strip()
            service = str(textsdict.get('service','')).strip()
            newname = f'{owner} {number} {physical} {line} {station} {service} {datestr}'.replace('  ',' ')

            new_tags=f'"{city}" {transport} "{number}"'
            
            for tag in [model, operator, station, line, region]:
                if tag:
                    new_tags += f' "{tag}"'

        
            
        if textsdict.get('more_tags','') != '':
            new_tags += ' '
            new_tags+=' '.join(self.more_tags_process(textsdict.get('more_tags','')))
            
        new_tags += ' namegenerated'
        olddesc=info['photo']['description']['_content']
        newdesc=olddesc
        if olddesc.strip()=='OLYMPUS DIGITAL CAMERA':
            olddesc=''
        if olddesc.strip()=='' and street != '':
            newdesc = street
        if desc != '': newdesc = desc 
        if street is not None and street != '': desc = desc + "\n"+street

        flickr.photos.setMeta(
            photo_id=photo_id,
            title=newname,
            description=newdesc
        )

        # Step 4: Update tags
        flickr.photos.setTags(
            photo_id=photo_id,
            tags=new_tags
        )
        

class FlickrBrowser(QWidget):
    def __init__(self,args):
        super().__init__()
        self.setWindowTitle("Flickr Image Browser")
        self.model = Model()
        self.args = args

        self.selecteds_list = list()
        
        self.backend = Backend()
        self.changeset = list()

        # Connect the signal to your method
        self.backend.imgSelected.connect(self.select_photo)
        self.backend.ShowImageOnMap.connect(self.ShowImageOnMap)
        self.backend.imgSelectedAppend.connect(self.select_photo_append)
        self.backend.imgMacros1.connect(self.on_macros1)
        self.backend.mapClick.connect(self.on_mapclick)
        self.wikidata_model = WikidataModel()
        
        #https://colorbrewer2.org/?type=qualitative&scheme=Paired&n=8
        
        self.palette=['#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00']
        
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
/* mark selected rows */
    .selected { background-color: orange; }
    .visited  { background-color: darkgray; }
    tr { transition: background-color 3.2s ease; }

        
        '''
        self.nominatim_keys=['country','state','county','city','village','hamlet','town','suburb','neighbourhood','road','house_number','name']
        self.gps_dest_folder = None
        self.images_coordinates_from_local_folder = None
        self.init_ui()
        self.flickr = self.authenticate_flickr()
        self.flickrimgs=list()
          


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
        middlelayout = QHBoxLayout()
        self.formcontainers = dict()
        self.formlayouts = dict()

        # search panel
        self.search_formcontainer=QGroupBox('Search images on flickr')
        layout.addWidget(self.search_formcontainer)
        self.search_formcontainer_layout = QHBoxLayout()
        self.search_formcontainer.setLayout(self.search_formcontainer_layout)
        # Input fields
        self.inputs_search = {}
        fields = ["tags", "tag_mode", "exclude", "min_taken_date", "max_taken_date","days","per_page"]
        for field in fields:
            row = QHBoxLayout()
            label = QLabel(field)
            edit = QLineEdit()
            if hasattr(self.args, field) and getattr(self.args, field) is not None:
                edit.setText(str(getattr(self.args, field)))
            self.inputs_search[field] = edit
            row.addWidget(label)
            row.addWidget(edit)
            self.search_formcontainer_layout.addLayout(row)

        self.inputs_search["tag_mode"].setPlaceholderText("all or any")
        #self.inputs_search["per_page"].setText(str(50))

        #self.inputs_search["days"].setPlaceholderText("number")
        #self.inputs_search["page"].setPlaceholderText("1")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_photos)
        self.search_formcontainer_layout.addWidget(self.search_btn)
        
        # select folder on disk to get GPS Destination
        self.formcontainers['gpsdest'] = QGroupBox('Select folder with source image files for get destination coordinates')
        self.formlayouts['gpsdest'] = QHBoxLayout()
        self.formcontainers['gpsdest'].setLayout(self.formlayouts['gpsdest'])
        layout.addWidget(self.formcontainers['gpsdest'])
        
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self.select_gpsdest_directory)
        self.formlayouts['gpsdest'].addWidget(browse_btn)
        

        # select folder on disk to get GPS Destination
        self.formcontainers['coords'] = QGroupBox('Coords')
        self.formlayouts['coords'] = QHBoxLayout()
        self.formcontainers['coords'].setLayout(self.formlayouts['coords'])
        layout.addWidget(self.formcontainers['coords'])
        browse_btn2 = QPushButton("Select folder with source image files for get destination coordinates")
        browse_btn2.clicked.connect(self.select_gpsdest_directory)
        self.formlayouts['coords'].addWidget(browse_btn2)
        
        self.wigets = dict()
        
        self.wigets['coords'] = QLineEdit()
        self.formlayouts['coords'].addWidget(QLabel('image coordinates:'))
        self.formlayouts['coords'].addWidget(self.wigets['coords'])
        self.wigets['coords-loadfromflickr']=QPushButton("Load coords from Flickr")
        self.wigets['coords-loadfromflickr'].clicked.connect(self.on_load_coord)
        self.formlayouts['coords'].addWidget(self.wigets['coords-loadfromflickr'])
        self.wigets['dest_coords'] = QLineEdit()
        self.formlayouts['coords'].addWidget(QLabel('destination coordinates:'))
        self.formlayouts['coords'].addWidget(self.wigets['dest_coords'])


        
        
        
        #selection panel
        self.selectedimgs_formcontainer=QGroupBox('Selected images')
        layout.addWidget(self.selectedimgs_formcontainer)
        self.selectedimgs_formcontainer_layout = QHBoxLayout()
        self.selectedimgs_formcontainer.setLayout(self.selectedimgs_formcontainer_layout)
        self.selections_label=QLabel()
        self.selections_label.setWordWrap(True)
        self.selectedimgs_formcontainer_layout.addWidget(self.selections_label)
        self.deselect_photos_button = QPushButton("Deselect all")
        self.deselect_photos_button.clicked.connect(self.deselect_photos)
        self.selectedimgs_formcontainer_layout.addWidget(self.deselect_photos_button)



        # display browser panel
        self.browser_main_table = QWebEngineView()
        self.browser_main_table.setFixedHeight(650)
        # do not focus on frist href after html set
        self.browser_main_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        #self.browser_main_table.page().settings().setAttribute(QWebEnginePage.WebAttribute.FocusOnNavigationEnabled, False)
        middlelayout.addWidget(self.browser_main_table)
        self.browser_main_table.setHtml("""<html><body><style>"""+self.css+"""</style><h1>wait for search result</h1>""", QUrl("qrc:/"))
        
        self.mappicker = QWebEngineView()
        self.mappicker.setFixedHeight(self.browser_main_table.height())
        self.mappicker.setMaximumWidth(450)
        # do not focus on frist href after html set
        self.mappicker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        middlelayout.addWidget(self.mappicker)
        self.mappicker.setHtml("""<html><body><style>"""+self.css+"""</style><h1>wait for select image</h1>""", QUrl("qrc:/"))
        
               
        # texts form
        self.formtab=QTabWidget()
        middlelayout.addWidget(self.formtab)
        self.formtab.setFixedWidth(400)
        layout.addLayout(middlelayout)
        
        
        # Create form tabs
        self.routelookup_buttons = {}
        self.geolookup_buttons = {}
        self.numlookup_buttons = {}
        self.geocode_rev_buttons = {}
        self.loaddestcoords_buttons = {}
        self.loadcoords_buttons = {}
        self.macros_buttons = {}
        self.formwritefields = {}
        self.formwritefields['tram']={}
        self.formtab.addTab(self.create_tram_tab(), "tram")
        self.formwritefields['trolleybus']={}
        self.formtab.addTab(self.create_trolleybus_tab(), "trolleybus")
        self.formwritefields['bus']={}
        self.formtab.addTab(self.create_bus_tab(), "bus")
        self.formwritefields['train']={}
        self.formtab.addTab(self.create_train_tab(), "train")
        self.formwritefields['automobile']={}
        self.formtab.addTab(self.create_automobile_tab(), "automobile")
        self.formwritefields["address"]={}
        self.formtab.addTab(self.create_address_tab(), "address")
        self.formwritefields["street"]={}
        self.formtab.addTab(self.create_street_tab(), "street")
        self.formwritefields["trainstation"]={}
        self.formtab.addTab(self.create_trainstation_tab(), "trainstation")
        self.formtab.setCurrentIndex(1)  # This makes "trolleybus" the default visible tab
        
     
        
        self.changeset_add_btn = QPushButton("Add to changeset")
        self.changeset_add_btn.setStyleSheet("background-color: "+self.palette[7])
        self.changeset_add_btn.clicked.connect(self.on_changeset_add)
        layout.addWidget(self.changeset_add_btn)
        
        self.changeset_write_btn = QPushButton("Write changeset")
        self.changeset_write_btn.setStyleSheet("background-color: "+self.palette[5])
        self.changeset_write_btn.clicked.connect(self.on_write_changeset)
        layout.addWidget(self.changeset_write_btn)

        

        
        self.setLayout(layout)
        
    def select_gpsdest_directory(self):
        # Show only directories
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose folder with original images with dest coordinates",
            "",                              # starting directory
            QFileDialog.Option.ShowDirsOnly  # only folders
        )
        if directory:
            # store the path in a self variable
            self.gps_dest_folder = directory
            # (optional) print or update UI
            print("Chosen folder:", self.gps_dest_folder)
            
        assert os.path.isdir(self.gps_dest_folder)
        self.images_coordinates_from_local_folder = self.read_images_dest_from_dir(self.gps_dest_folder)
        pass

        
        
    def read_images_dest_from_dir(self,directory: str) -> list[dict]:
        # read exif from all files in folder
        # get gps dest coordinates, if exist
        # save to dict with key is timestamp with stripped timezone
        # if two images taken in same second - do not save both.
    
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        from dateutil import parser

        def _dms_to_dd(dms, ref):
            """
            Convert GPS coordinates from DMS to decimal degrees.

            Args:
                dms: sequence of three elements (deg, min, sec). Each element can be:
                    - a float or int
                    - a rational-like object with .numerator and .denominator
                ref: hemisphere reference, one of 'N', 'S', 'E', 'W'

            Returns:
                float: decimal degrees (negative for 'S' or 'W')
            """
            def to_float(x):
                # handle rational-like objects
                if hasattr(x, "numerator") and hasattr(x, "denominator"):
                    return x.numerator / x.denominator
                # fallback for float/int or anything else castable
                return float(x)

            deg, minutes, seconds = map(to_float, dms)
            dd = deg + minutes / 60.0 + seconds / 3600.0

            return -dd if ref in ("S", "W") else dd

        from dateutil import parser
        records = []
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            try:
                img = Image.open(filepath)
                exif = img._getexif() or {}

                dt = None
                gps_dest_lat = None
                gps_dest_lon = None
                gps_lat = None
                gps_lon = None

                # First pass: find DateTimeOriginal and raw GPSInfo block
                raw_gps = None
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'DateTimeOriginal':
                        # replace only first two colons so parser accepts YYYY-MM-DD HH:MM:SS
                        dt = parser.parse(value.replace(":", "-", 2))
                        dt = dt.replace(microsecond=0)
                        if dt.tzinfo:
                            dt = dt.replace(tzinfo=None)

            
                    elif tag == 'GPSInfo':
                        raw_gps = value

                # Second pass: decode GPS tags and pull out destination coords
                if raw_gps:
                    gps = {}
                    for t, val in raw_gps.items():
                        key = GPSTAGS.get(t, t)
                        gps[key] = val

                    if 'GPSDestLatitude' in gps and 'GPSDestLongitude' in gps:
                        lat_ref = gps.get('GPSDestLatitudeRef', 'N')
                        lon_ref = gps.get('GPSDestLongitudeRef', 'E')
                        gps_dest_lat = _dms_to_dd(gps['GPSDestLatitude'], lat_ref)
                        gps_dest_lon = _dms_to_dd(gps['GPSDestLongitude'], lon_ref)

                    if 'GPSLatitude' in gps and 'GPSLongitude' in gps:
                        lat_ref = gps.get('GPSLatitudeRef', 'N')
                        lon_ref = gps.get('GPSLongitudeRef', 'E')
                        gps_lat = _dms_to_dd(gps['GPSLatitude'], lat_ref)
                        gps_lon = _dms_to_dd(gps['GPSLongitude'], lon_ref)

                
                record = {}
                record['filepath'] = filepath
                record['filename'] = filename
                record['datetime'] = dt
                if gps_dest_lat is not None:
                    record["gps_dest_latitude"] = gps_dest_lat
                if gps_dest_lon is not None:
                    record["gps_dest_longitude"] = gps_dest_lon
                if gps_lat is not None:
                    record["gps_latitude"] = gps_lat
                if gps_lon is not None:
                    record["gps_longitude"] = gps_lon    
                    
                if dt and (gps_dest_lat is not None and gps_dest_lon is not None):
                    records.append(record)
            except:
                continue
        # delete records with non-unique datetime
        # if two images taken in same second - no keep it coordinates, it is too complicated
        import collections
        dt_counts = collections.Counter(rec['datetime'] for rec in records)
        # 2. Фильтруем: оставляем только записи, у которых dt встречается ровно 1 раз
        filtered = [rec for rec in records if dt_counts[rec['datetime']] == 1]
        records = filtered
        del filtered
        records_by_datetime = { rec['datetime']: rec for rec in records }
        return records_by_datetime


        
    def create_tram_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        # Add text fields
        
        for label in ["preset","city","operator","model", "number", "route","street",  'desc', 'more_tags']:
            line_edit = QLineEdit()
            if label=="preset":
                line_edit.setText('tram')
            self.formwritefields['tram'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
            if label=="street":
                self.geolookup_buttons['tram']=dict()
                self.geolookup_buttons['tram']["street"]=QPushButton("⇪ geolookup_street ⇪")
                self.geolookup_buttons['tram']["street"].clicked.connect(self.on_geolookup_street)
                form_layout.addRow(":", self.geolookup_buttons['tram']["street"])
            if label=='number':
                self.numlookup_buttons['tram']=dict()
                self.numlookup_buttons['tram']['number']=QPushButton("⇪ take num from name prefix ⇪")
                self.numlookup_buttons['tram']['number'].clicked.connect(self.on_numlookup)
                form_layout.addRow(":", self.numlookup_buttons['tram']['number'])
            if label=='route':
                self.routelookup_buttons['tram']=dict()
                self.routelookup_buttons['tram']['number']=QPushButton("⇪ take num and route from name prefix ⇪")
                self.routelookup_buttons['tram']['number'].clicked.connect(self.on_prefixlookup)
                form_layout.addRow(":", self.routelookup_buttons['tram']['number'])
                


        tab.setLayout(form_layout)
        return tab

    def create_trolleybus_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()
        
        transport='trolleybus'
        for label in ["preset","city","operator", "number", "model","route","street", 'desc',  'more_tags']:
            line_edit = QLineEdit()
            if label=="preset":
                line_edit.setText(transport)
            self.formwritefields[transport][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
            if label=="street":
                self.geolookup_buttons[transport]=dict()
                self.geolookup_buttons[transport]["street"]=QPushButton("⇪ geolookup_street ⇪")
                self.geolookup_buttons[transport]["street"].clicked.connect(self.on_geolookup_street)
                form_layout.addRow(":", self.geolookup_buttons[transport]["street"])
            if label=='number':
                self.numlookup_buttons[transport]=dict()
                self.numlookup_buttons[transport]['number']=QPushButton("⇪ take num from name prefix ⇪")
                self.numlookup_buttons[transport]['number'].clicked.connect(self.on_numlookup)
                form_layout.addRow(":", self.numlookup_buttons[transport]['number'])
            if label=='route':
                self.routelookup_buttons[transport]=dict()
                self.routelookup_buttons[transport]['number']=QPushButton("⇪ take route from name prefix ⇪")
                self.routelookup_buttons[transport]['number'].clicked.connect(self.on_routelookup)
                form_layout.addRow(":", self.routelookup_buttons[transport]['number'])
                
        tab.setLayout(form_layout)
        return tab

    def create_bus_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()
        transport='bus'

        for label in ["preset","city","operator", "number","numberplate", "model","route","street",'desc',   'more_tags']:
            line_edit = QLineEdit()
            if label=="preset":
                line_edit.setText('bus')
            self.formwritefields['bus'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
            if label=="street":
                self.geolookup_buttons[transport]=dict()
                self.geolookup_buttons[transport]["street"]=QPushButton("⇪ geolookup_street ⇪")
                self.geolookup_buttons[transport]["street"].clicked.connect(self.on_geolookup_street)
                form_layout.addRow(":", self.geolookup_buttons[transport]["street"])
            if label=='number':
                self.numlookup_buttons[transport]=dict()
                self.numlookup_buttons[transport]['number']=QPushButton("⇪ take num from name prefix ⇪")
                self.numlookup_buttons[transport]['number'].clicked.connect(self.on_numlookup)
                form_layout.addRow(":", self.numlookup_buttons[transport]['number'])
            if label=='route':
                self.routelookup_buttons[transport]=dict()
                self.routelookup_buttons[transport]['number']=QPushButton("⇪ take route from name prefix ⇪")
                self.routelookup_buttons[transport]['number'].clicked.connect(self.on_routelookup)
                form_layout.addRow(":", self.routelookup_buttons[transport]['number'])             
        tab.setLayout(form_layout)
        return tab    

    def create_address_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["preset","zoom","lang_int","lang_loc","venue_int",'name_template','desc_template','tags_template','name','desc','tags', 'more_tags']:
            line_edit = QLineEdit()
            self.formwritefields['address'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
            if label=='name':
                self.geocode_rev_buttons['address']=QPushButton("⇪ Nominatim query ⇪")
                self.geocode_rev_buttons['address'].clicked.connect(self.on_geocode_reverse_address)
                self.geocode_rev_buttons['address'].setStyleSheet("background-color: "+self.palette[6])
                form_layout.addRow(":", self.geocode_rev_buttons['address'])
               
            if label=='dest_coordinates':
                self.loaddestcoords_buttons['address']=QPushButton("⇪ take destination coordinates from image originals ⇪")
                self.loaddestcoords_buttons['address'].clicked.connect(self.on_load_dest_coord)
                form_layout.addRow(":", self.loaddestcoords_buttons['address'])
                self.loadcoords_buttons['address']=QPushButton("⇪ take coordinates from flickr ⇪")
                self.loadcoords_buttons['address'].clicked.connect(self.on_load_coord)
                form_layout.addRow(":", self.loadcoords_buttons['address'])
            if label == 'more_tags':
                self.macros_buttons['address-stage-next-revgeocode'] = QPushButton("Macros | add current file to changeset - go next - load destinstion coordinates - Nominatim query") 
                self.macros_buttons['address-stage-next-revgeocode'].clicked.connect(self.on_macros1)
                form_layout.addRow(":", self.macros_buttons['address-stage-next-revgeocode'])              
                
                self.macros_buttons['nominatim-stage'] = QPushButton("Macros | nominatim-stage") 
                self.macros_buttons['nominatim-stage'].clicked.connect(self.on_macros2)
                self.macros_buttons['nominatim-stage'].setStyleSheet("background-color: "+self.palette[7])
                form_layout.addRow(":", self.macros_buttons['nominatim-stage'])  
                             
                self.macros_buttons['nominatim-stage-save'] = QPushButton("Macros | nominatim-stage-save") 
                self.macros_buttons['nominatim-stage-save'].clicked.connect(self.on_macros3)
                self.macros_buttons['nominatim-stage-save'].setStyleSheet("background-color: "+self.palette[5])
                form_layout.addRow(":", self.macros_buttons['nominatim-stage-save'])  
        self.formwritefields['address']['preset'].setText('address')   
        self.formwritefields['address']['lang_int'].setText('en')
        self.formwritefields['address']['lang_loc'].setText('ru')
        self.formwritefields['address']['zoom'].setText('18')
        self.formwritefields['address']['name_template'].setText('{village_int}{hamlet_int}{city_int}{town_int} {road_int} {house_number_int}')
        self.formwritefields['address']['desc_template'].setText('{venue_int} {village_loc}{hamlet_loc}{city_loc}{town_loc} {road_loc} {house_number_loc} {name_int}')
        self.formwritefields['address']['tags_template'].setText('{venue_int},{village_int},{hamlet_int},{city_int},{name_loc},{road_int},{country_int},{suburb_int},{town_int},{state_int},{neighbourhood_int},building')
        
        
        nominatim_keys_list = QLabel()
        nominatim_keys_list.setText(', '.join(self.nominatim_keys))
        form_layout.addRow('nominatim keys list: ',nominatim_keys_list)
        tab.setLayout(form_layout)
        return tab    

    def create_street_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["preset","dest_coordinates","lang_int","lang_loc",'owner','city','suburb_int','road_loc','road_int','desc','out-name','out-desc', 'more_tags']:
            line_edit = QLineEdit()
            self.formwritefields['street'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)

            if label=='road_int':
                self.geocode_rev_buttons['street']=QPushButton("⇪ Nominatim query ⇪")
                self.geocode_rev_buttons['street'].clicked.connect(self.on_geocode_reverse_street)
                self.geocode_rev_buttons['street'].setStyleSheet("background-color: #e7298a")
                form_layout.addRow(":", self.geocode_rev_buttons['street'])
                
        self.formwritefields['street']['preset'].setText('street')   
        self.formwritefields['street']['lang_int'].setText('en')
        self.formwritefields['street']['lang_loc'].setText('ru')

        nominatim_keys_list = QLabel()
        nominatim_keys_list.setText(', '.join(self.nominatim_keys))
        form_layout.addRow('nominatim keys list: ',nominatim_keys_list)
        tab.setLayout(form_layout)
        return tab    
    
    def create_trainstation_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["preset","dest_coordinates","lang_int","lang_loc",'owner','city','name','desc', 'more_tags']:
            line_edit = QLineEdit()
            self.formwritefields['trainstation'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)

            if label=='dest_coordinates':
                self.loaddestcoords_buttons['trainstation']=QPushButton("⇪ take destination coordinates from image originals ⇪")
                self.loaddestcoords_buttons['trainstation'].clicked.connect(self.on_load_dest_coord)
                form_layout.addRow(":", self.loaddestcoords_buttons['trainstation'])
                
        self.formwritefields['trainstation']['preset'].setText('trainstation')   
        self.formwritefields['trainstation']['lang_int'].setText('en')
        self.formwritefields['trainstation']['lang_loc'].setText('ru')
        #self.formwritefields['trainstation']['name_template'].setText('{venue_int} {city_int} {road_int} {house_number_int}')
        #self.formwritefields['trainstation']['desc_template'].setText('{venue_int} {city_loc} {road_loc} {house_number_loc}')
        #self.formwritefields['trainstation']['tags_template'].setText('{city_int},{country_int},{suburb_int},{town_int},{village_int},{state_int},{neighbourhood_int},building')
        
        
        nominatim_keys_list = QLabel()
        nominatim_keys_list.setText(', '.join(self.nominatim_keys))
        form_layout.addRow('nominatim keys list: ',nominatim_keys_list)
        tab.setLayout(form_layout)
        return tab    
    
    def create_automobile_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["preset","city","brand", "numberplate", "model","suburb_int","road_int","road_loc", 'desc', 'more_tags','dest_coordinates','lang_loc','lang_int']:
            line_edit = QLineEdit()
            if label=="preset":
                line_edit.setText('automobile')
            self.formwritefields['automobile'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
            if label=='road_loc':
                self.geocode_rev_buttons['automobile']=dict()
                self.geocode_rev_buttons['automobile']=QPushButton("⇪ Street from Nominatim query ⇪")
                self.geocode_rev_buttons['automobile'].clicked.connect(self.on_geocode_reverse_street)
                self.geocode_rev_buttons['automobile'].setStyleSheet("background-color: #e7298a")
                form_layout.addRow(":", self.geocode_rev_buttons['automobile'])
        self.formwritefields['automobile']['lang_int'].setText('en')
        self.formwritefields['automobile']['lang_loc'].setText('ru')
        tab.setLayout(form_layout)
        return tab  

    def create_train_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["preset","physical","owner","number","station","city","model","line","service", 'desc',  'more_tags']:
            line_edit = QLineEdit()
            if label=="preset":
                line_edit.setText('train')
            self.formwritefields['train'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
        tab.setLayout(form_layout)
        return tab    
        
    def on_changeset_add(self):
        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)

        textsdict = {field: widget.text() for field, widget in self.formwritefields[current_tab_name].items()}
        flickrid=''
        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                self.changeset.append({'id':flickrid, 'textsdict':textsdict})
            self.deselect_photos()
        else:
            QMessageBox.warning(self, "Invalid data", "Select photo frist")
        
        
    def on_write_changeset(self):
    
        if len(self.changeset)>0:
            for change in self.changeset:
                try:
                    if change['textsdict']["preset"]== 'address':
                        self.model.address_image_flickr_update(self.flickr, change['id'], change['textsdict'])       
                    elif change['textsdict']["preset"]== 'street':
                        self.model.street_image_flickr_update(self.flickr, change['id'], change['textsdict'])   
                    else:
                        self.model.transport_image_flickr_update(self.flickr, change['id'], change['textsdict'])
                except:
                    continue
            self.changeset = list()
        else:
            QMessageBox.warning(self, "Invalid data", "Make edits frist")
            
    

    def on_prefixlookup(self):
        self.on_numlookup()
        self.on_routelookup()   
    def on_numlookup(self):
        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)

        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                for img in self.flickrimgs: 
                    if img['id'] == flickrid:
                        text=img['title']
                        text = text.replace('_',' ')
                        text = text[:text.find(' ')]
                        self.formwritefields[current_tab_name]['number'].setText(text)
                        return
           
    def on_routelookup(self):
        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)

        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                for img in self.flickrimgs: 
                    if img['id'] == flickrid:                      
                        import re

                        regex = r"_(?:r|м)(\d+)(?:_[^.]+)?$"
                        test_str = img['title']
                        route=''

                        matches = re.finditer(regex, test_str, re.MULTILINE)
                        for match in matches:
                            result = match.group(1)
                            if "eplace" in result:
                                continue
                            route = result
                            del result
                        if route == "z":
                            route = None
                
                        self.formwritefields[current_tab_name]['route'].setText(route)
                        return
              

    def escape4flickr_tag(self,text):
        if ' ' in text:
            text = '"'+text+'"'
        return text
    
    def on_macros1(self):
        self.on_load_dest_coord()
        self.on_geocode_reverse_address()
    
    def on_macros2(self):
        self.on_geocode_reverse_address()
        self.on_changeset_add()
    
    def on_macros3(self):
        self.on_geocode_reverse_address()
        self.on_changeset_add()
        self.on_write_changeset()
                
    def on_mapclick(self,lat,lon):
        self.wigets['dest_coords'].setText(f"{lat},{lon}")
 
    def on_load_coord(self):
        from dateutil import parser
        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)

        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                for img in self.flickrimgs: 
                    if img['id'] == flickrid:
                        if 'dest_coordinates' in  self.formwritefields[current_tab_name]:
                            self.formwritefields[current_tab_name]['dest_coordinates'].setText(f"{img['latitude']},{img['longitude']}")
                        self.wigets['coords'].setText(f"{img['latitude']},{img['longitude']}")
                        return
           
           
    def on_load_dest_coord(self):
        from dateutil import parser
        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)

        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                for img in self.flickrimgs: 
                    if img['id'] == flickrid:
                        #dt = parser.parse(img.get('datetaken').replace(":", "-", 2))
                        dt = parser.parse(img.get('datetaken'))
                        dt = dt.replace(microsecond=0)
                        if dt.tzinfo:
                            dt = dt.replace(tzinfo=None)

                        if self.images_coordinates_from_local_folder is None:
                            self.formwritefields[current_tab_name]['dest_coordinates'].setText('no loaded folder')
                            return
                        source_image_record = self.images_coordinates_from_local_folder.get(dt)
                        if source_image_record is not None:
                            if 'gps_dest_latitude' in  source_image_record and 'gps_dest_longitude' in source_image_record: 
                                self.formwritefields[current_tab_name]['dest_coordinates'].setText(f"{source_image_record['gps_dest_latitude']},{source_image_record['gps_dest_longitude']}")
                                self.wigets['dest_coords'].setText(f"{source_image_record['gps_dest_latitude']},{source_image_record['gps_dest_longitude']}")
                        return
           
           

                        
                        
                        
    def on_geocode_reverse_address(self,zoom=19):
        # Configure geocoder with 1 req/sec limit
        geolocator = Nominatim(user_agent="trolleway_image_names_geocode", timeout=10)
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)

        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)
        
        

        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                for img in self.flickrimgs: 
                    if img['id'] == flickrid:
                        
                        # lookup
                        lat = float(img['latitude'])
                        lon = float(img['longitude'])
                        coords = (lat,lon)
                        dest_coords_str = self.wigets['dest_coords'].text().strip()
                        if 'zoom' in self.formwritefields[current_tab_name]:
                            zoom=self.formwritefields[current_tab_name]['zoom'].text().strip()
                        if dest_coords_str != '' and ',' in dest_coords_str: 
                            coords = dest_coords_str
                        
                        lang_loc = self.formwritefields[current_tab_name]['lang_loc'].text()
                        lang_int = self.formwritefields[current_tab_name]['lang_int'].text()
                        
                        geocoderesults={}
                        try:
                            geocoderesults['loc'] = geolocator.reverse(coords,exactly_one=True,language=lang_loc,addressdetails=True,zoom=zoom)
                            geocoderesults['int'] = geolocator.reverse(coords,exactly_one=True,language=lang_int,addressdetails=True,zoom=zoom)
                        except:
                            return
                        if not geocoderesults['loc']:
                            return                        
                        if not geocoderesults['int']:
                            return  
                        replaces={'int':{},'loc':{}}
                        for key in self.nominatim_keys:
                            
                            replaces['loc'][key]=geocoderesults['loc'].raw.get('address',{}).get(key,'')
                            
                            
                            if lang_loc in get_available_language_codes():
                                replaces['int'][key]=translit(geocoderesults['int'].raw.get('address',{}).get(key,''),lang_loc,reversed=True)
                                replaces['int'][key] = replaces['int'][key].replace("'",'')
                            else:
                                replaces['int'][key]=geocoderesults['int'].raw.get('address',{}).get(key,'')
                        
                        # venue
                        replaces['int']['venue']=self.formwritefields[current_tab_name]['venue_int'].text()
                        
                        # name
                        fmt=self.formwritefields[current_tab_name]['name_template'].text()
                        txt=fmt
                        for fld,val in replaces['int'].items():
                            txt = txt.replace('{'+fld+'_int}',val)
                        for fld,val in replaces['loc'].items():
                            txt = txt.replace('{'+fld+'_loc}',val)
                        txt = txt.strip()
                        txt = re.sub(' +', ' ', txt)
                        self.formwritefields[current_tab_name]['name'].setText(txt)
                        
                        # desc
                        fmt=self.formwritefields[current_tab_name]['desc_template'].text()
                        txt=fmt
                        for fld,val in replaces['int'].items():
                            txt = txt.replace('{'+fld+'_int}',val)
                        for fld,val in replaces['loc'].items():
                            txt = txt.replace('{'+fld+'_loc}',val)
                        txt = txt.strip()
                        txt = re.sub(' +', ' ', txt)
                        self.formwritefields[current_tab_name]['desc'].setText(txt)
                        
                        # tags
                        fmt=self.formwritefields[current_tab_name]['tags_template'].text()
                        txt=fmt
                        txt = txt.strip()
                        txt = re.sub(' +', ' ', txt) #merge multiple space to single space
                        
                        for fld,val in replaces['int'].items():
                            txt = txt.replace('{'+fld+'_int}',self.escape4flickr_tag(val))
                            if 'district' in val.lower():
                                txt = txt +','+ self.escape4flickr_tag(val.lower().replace('district','').strip())
                        for fld,val in replaces['loc'].items():
                            txt = txt.replace('{'+fld+'_loc}',self.escape4flickr_tag(val))
                        txt = re.sub(',+', ',', txt) #merge multiple , to single ,
                        self.formwritefields[current_tab_name]['tags'].setText(txt)
                        
        
    def on_geocode_reverse_street(self):
        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)
        lang_loc = self.formwritefields[current_tab_name]['lang_loc'].text()
        lang_int = self.formwritefields[current_tab_name]['lang_int'].text()
        
        c = ''
        c = self.wigets['dest_coords'].text().strip()
        if c == '':
            c = self.wigets['coords'].text().strip()
            if c == '':
                QMessageBox.warning(self, "no coordinates", "click on map to get street name")
                return
       
        geocode_result = self.geocode_street(c,lang_loc,lang_int)
        if geocode_result is not None:    
            road_loc,road_int,suburb_int = geocode_result
            self.formwritefields[current_tab_name]['road_int'].setText(road_int)
            self.formwritefields[current_tab_name]['road_loc'].setText(road_loc)
            if 'suburb_int' in self.formwritefields[current_tab_name]:
                self.formwritefields[current_tab_name]['suburb_int'].setText(suburb_int)
        
    def geocode_street(self,coords:str,lang_loc:str,lang_int:str):    
        geolocator = Nominatim(user_agent="trolleway_image_names_geocode", timeout=10)
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)
        if coords != '' and ',' in coords: 
            coords = coords
        else:
            return 'set dest coords frist','set dest coords frist'
        
        geocoderesults={}
        try:
            geocoderesults['loc'] = geolocator.reverse(coords,exactly_one=True,language=lang_loc,addressdetails=True,zoom=16)
            geocoderesults['int'] = geolocator.reverse(coords,exactly_one=True,language=lang_int,addressdetails=True,zoom=16)
        except:
            return
        if not geocoderesults['loc']:
            return                        
        if not geocoderesults['int']:
            return
        
        road_loc = geocoderesults['loc'].raw.get('address',{}).get('road','')
        road_int =translit( geocoderesults['int'].raw.get('address',{}).get('road',''),lang_loc,reversed=True)
        suburb_int =translit( geocoderesults['int'].raw.get('address',{}).get('suburb',''),lang_loc,reversed=True)
        
        return road_loc, road_int,suburb_int
        

    def on_geolookup_street(self):
        current_tab_index = self.formtab.currentIndex()
        current_tab_name = self.formtab.tabText(current_tab_index)

        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                for img in self.flickrimgs: 
                    if img['id'] == flickrid:
                        
                        # lookup

                        lat = float(img['latitude'])
                        lon = float(img['longitude'])

                        # Define a small buffer (in degrees) around the point
                        delta = 0.00001 

                        # Create the rectangle coordinates (clockwise or counter-clockwise)
                        rectangle_coords = [
                            (lon - delta, lat - delta),
                            (lon - delta, lat + delta),
                            (lon + delta, lat + delta),
                            (lon + delta, lat - delta),
                            (lon - delta, lat - delta)  # Close the polygon
                        ]

                        # Convert to WKT polygon string
                        wkt_string = 'POLYGON((' + ', '.join([f'{x} {y}' for x, y in rectangle_coords]) + '))'
                        ngw_url='https://trolleway.nextgis.com'
                        ngw_layer=5820

                        payload={'srs':4326, 'geom':wkt_string,  "layers":list([ngw_layer])}
                        url=ngw_url+'/api/feature_layer/identify'
                        request = requests.post(url, json = payload)
                        
                        wdid=None
                        text=''

                        if request.status_code == 200:
                            try:
                                response = request.json()
                                print(response)
                                r=response.get(str(ngw_layer))
                                r=r.get('features')
                                if r is not None:
                                    r=r[0]
                                    r=r.get('fields')
                                    wdid=r.get('wikidata')
                                    text = self.wikidata_model.get_name(wdid)
                                    self.formwritefields[current_tab_name]["street"].setText(text)
                            except:
                                self.formwritefields[current_tab_name]["street"].setText('')
                        else:
                            self.formwritefields[current_tab_name]["street"].setText('')


        


    def reset_search_results(self):
        self.browser_main_table.setHtml('''<html><body><h1>wait for query execute</h1>''', QUrl("qrc:/"))
        pass
    
    def search_photos(self,SORTMODE = 'datetaken',skip_if_namegenerated=True):
        #self.get_photos_from_album('72177720327428694')
        #return
        self.reset_search_results()
        trs=''

        params = {"extras": "date_taken,tags,geo,url_o"}
        for key, widget in self.inputs_search.items():
            val = widget.text().strip()
            if key == 'exclude':
                exclude_tags = val
                continue
            if val:
                params[key] = val
        
        tags4query=params.get('tags','')
        #params.pop("tags", None)

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
        params['per_page']=int(params['per_page'])
        #params['page'] = 1
        params['content_types']='0'

        #params['page']=1
        photos = self.flickr.photos.search(**params)
        #result_list=photos["photos"]["photo"]
        
        result_list = list()
        gonextpage=True
        page_counter=0
        while(gonextpage):
            page_counter = page_counter+1
            params['page']=page_counter
            photos = self.flickr.photos.search(**params)

            result_list_page=photos["photos"]["photo"]
            result_list=result_list+result_list_page
            gonextpage=False
            if len(result_list_page)>0 and photos['photos']['pages']>page_counter:
                gonextpage=True
        

        
        self.flickrimgs=list()
        if len(result_list)==0:
            self.info_search_noresults()
        else:
            if SORTMODE == 'datetaken':
                result_list = sorted(result_list, key=lambda x: x["datetaken"], reverse=False)
            elif SORTMODE == 'lon':
                result_list = sorted(result_list, key=lambda x: float(x["longitude"]), reverse=False)
            elif SORTMODE == 'lat':
                result_list = sorted(result_list, key=lambda x: float(x["latitude"]), reverse=True)
            else:
                result_list = sorted(result_list, key=lambda x: x["datetaken"], reverse=False)
            
            files_to_display=0
            for photo in result_list:
                #for photo in sorted(photos["photos"]["photo"], key=lambda d: d['datetaken']):
                 
                if ('namegenerated' in photo['tags'] and skip_if_namegenerated) and 'noname' not in photo['tags']:
                    continue
                if len(exclude_tags) > 0:
                    if ',' in exclude_tags:
                        etl=exclude_tags.split(',')
                    else:
                        etl=list()
                        etl.append(exclude_tags)
                    tags4search=list()
                    tags4search=[tag.strip().strip('"') for tag in photo['tags'].split(' ')]
                    if any(elem in etl for elem in tags4search):
                        continue                 

                if tags4query != '':
                    tags4search=list()
                    tags4search=[tag.strip().strip('"') for tag in photo['tags'].split(' ')]
                    if not any(elem in tags4query for elem in tags4search):
                        continue
                    if photo['tags']=='':
                        continue

                    # for all mode all(elem in list2 for elem in list1)

                trs+=self.gen_photo_row(photo)
                files_to_display = files_to_display + 1
        
        html="""<html>       <head>
            <style>
"""+self.css+"""
    </style>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                let backend;
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    backend = channel.objects.backend;
                });


            function handleSelectImg(button, imageId) {
                backend.handle_select_img(imageId);
                /* mark selected row */
                const tr = button.closest('tr');
                tr.classList.remove('visited');
                tr.classList.add('selected');

                /* update other rows */
                const allRows = document.querySelectorAll('table tr');
                allRows.forEach(row => {
                    if (row !== tr && row.classList.contains('selected')) {
                        row.classList.remove('selected');
                        row.classList.add('visited');
                    }
                }); 
            }

            function handleSelectImgAppend(button, imageId) {
                backend.handle_select_img_append(imageId);
                /* mark selected row */
                const tr = button.closest('tr');
                tr.classList.remove('visited');
                tr.classList.add('selected');

                /* no update other rows */

            }
                
                function handleShowImageOnMap(button, imageId) {
                    backend.handle_ShowImageOnMap(imageId);
                }      
                function handleMacros1(button, imageId) {
                    backend.handleMacros1(imageId);
                    /* mark selected row */
                    const tr = button.closest('tr');
                    tr.classList.add('selected');
                }         
                
                function decelectImg(imageId) {
                  const tr = document.getElementById(imageId);
                  if (!tr) return;
                  tr.classList.remove('selected');
                  tr.classList.add('visited');
                }
            </script>
        </head><body><table>"""
        html+='<p style="font-face: monospace;">Get images from server: '+str(len(result_list))+'</p>'
        html+='<p style="font-face: monospace;">Displayed images: '+str(files_to_display)+'</p>'
        html+=trs
        html+='</table>'

        html+='</html>'
        
        with open("debug.htm", "w", encoding="utf-8") as f:
            f.write(html)
    
        self.browser_main_table.setPage(ExternalLinkPage(self.browser_main_table))
        self.browser_main_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.browser_main_table.setHtml(html, QUrl("qrc:/"))
        

        self.web_channel = QWebChannel()
        self.web_channel.registerObject("backend", self.backend)
        self.browser_main_table.page().setWebChannel(self.web_channel)
        self.flickrimgs=result_list


    def info_search_noresults(self):
        QMessageBox.warning(self, "Not found", "Select photo return no results")
    def gen_photo_row(self,photo):
        tr=''

        image_url = f"https://live.staticflickr.com/{photo['server']}/{photo['id']}_{photo['secret']}_w.jpg"
        image_url_o = f"{photo['url_o']}"
        geo_text=''
        if photo['latitude']==0: 
            geo_text='🌍❌'
        photo_url = f"https://www.flickr.com/photos/{photo['owner']}/{photo['id']}/in/datetaken/"
        info = f'''{photo['title']}{geo_text} {photo['datetaken']} <br><a href="{photo_url}" tabindex="-1"> Open on Flickr</a><br/><a href="{image_url_o}" tabindex="-1">jpeg origin</a>'''
        info += ''' <a href="https://www.flickr.com/photos/organize/?ids='''+photo['id']+'''">Organizr</a></br>'''
        geocodezoom=18
        if photo['latitude']!=0:
            info += f'''<br/><a href="https://yandex.ru/maps/?panorama[point]={photo['longitude']},{photo['latitude']}">Y pano</a> <a href="https://yandex.ru/maps/?whatshere[point]={photo['longitude']},{photo['latitude']}&whatshere[zoom]=19">Y Map</a> <br><a href="https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={photo['latitude']}&lon={photo['longitude']}&zoom={geocodezoom}&addressdetails=1">Rev geocode</a>'''
        
        tr=f'''<tr id="{photo['id']}"><td><img src="{image_url}"></td><td>{info}<br/><button tabindex="-1" onclick="handleSelectImg(this,'{photo['id']}')">Select</button><button tabindex="-1" onclick="handleSelectImgAppend(this,'{photo['id']}')">Append to select</button><button tabindex="-1" onclick="handleShowImageOnMap(this,'{photo['id']}')">Select and move map</button><button tabindex="-1" onclick="handleMacros1(this,'{photo['id']}')">Macros</button></td></tr>'''+"\n"
        return tr

    def openlayers_map_refresh(self,lat,lon):
        openlayers_html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>OpenLayers Map</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  html, body, #map { margin:0; padding:0; height:100%; width:100%; }
  .marker-label { background: rgba(255,255,255,0.8); padding:2px 4px; border-radius:3px; border:1px solid #666; }
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@7.4.0/ol.css" />
<script src="https://cdn.jsdelivr.net/npm/ol@7.4.0/dist/ol.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>

</head>
<body>
<div id="map"></div>
<script>
let map, vectorSource, vectorLayer;
let destFeature = null;

function initMap() {
    vectorSource = new ol.source.Vector();
    vectorLayer = new ol.layer.Vector({ source: vectorSource });
    map = new ol.Map({
        target: 'map',
        layers: [
            new ol.layer.Tile({ source: new ol.source.OSM() }),
            vectorLayer
        ],
        view: new ol.View({
            center: ol.proj.fromLonLat([$lon, $lat]),
            zoom: 18
        })
    });

map.on('singleclick', function(evt) {
    let coord = ol.proj.toLonLat(evt.coordinate);
    if (evt.originalEvent && evt.originalEvent.shiftKey) {
        placeDestination(coord[1], coord[0]);
        if (window.pyObj && window.pyObj.shiftClicked) {
            window.pyObj.shiftClicked(coord[1], coord[0]);
        }
    } else {
        placeMarker(coord[1], coord[0], 'Image');
        if (window.pyObj && window.pyObj.olimageClicked) {
            window.pyObj.olimageClicked(coord[1], coord[0]);
        }
    }
});
}

function clearMarkers() {
    vectorSource.clear();
    destFeature = null;
}

function placeMarker(lat, lon, label) {
    clearMarkers();
    let feature = new ol.Feature({
        geometry: new ol.geom.Point(ol.proj.fromLonLat([lon, lat]))
    });
    feature.setStyle(new ol.style.Style({
        image: new ol.style.Circle({ radius: 8, fill: new ol.style.Fill({color: '#ff0000'}), stroke: new ol.style.Stroke({color:'#fff', width:2}) }),
        text: new ol.style.Text({ text: label || '', offsetY: -20, fill: new ol.style.Fill({color:'#000'}), backgroundFill: new ol.style.Fill({color:'rgba(255,255,255,0.8)'}) })
    }));
    vectorSource.addFeature(feature);
    map.getView().animate({center: ol.proj.fromLonLat([lon, lat]), zoom: 18,duration:100});
}

function placeDestination(lat, lon) {
    if (destFeature) {
        vectorSource.removeFeature(destFeature);
        destFeature = null;
    }
    destFeature = new ol.Feature({
        geometry: new ol.geom.Point(ol.proj.fromLonLat([lon, lat]))
    });
    destFeature.setStyle(new ol.style.Style({
        image: new ol.style.Icon({ src: 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28"><circle cx="14" cy="14" r="10" fill="%23007bff" stroke="%23fff" stroke-width="2"/></svg>' }),
        text: new ol.style.Text({ text: 'Destination', offsetY: -20, fill: new ol.style.Fill({color:'#000'}) })
    }));
    vectorSource.addFeature(destFeature);
}

new QWebChannel(qt.webChannelTransport, function(channel) {
    window.pyObj = channel.objects.pyObj;
    window.pyObj.placeMarker.connect(function(lat, lon, label) {
        placeMarker(lat, lon, label);
    });
    window.pyObj.clearMarkers.connect(function() {
        clearMarkers();
    });
    window.pyObj.placeDestination.connect(function(lat, lon) {
        placeDestination(lat, lon);
    });
});

initMap();
</script>
</body>
</html>
"""
        # ensure lat/lon are strings for replace
        openlayers_html = openlayers_html.replace('$lat', str(lat)).replace('$lon', str(lon))

        # create and attach web channel with the same object name used in JS ("pyObj")
        self.web_channel_mappicker = QWebChannel()
        self.web_channel_mappicker.registerObject("pyObj", self.backend)
        self.mappicker.page().setWebChannel(self.web_channel_mappicker)
        self.mappicker.setHtml(openlayers_html, QUrl("qrc:/"))

        # Now emit the initial marker after the webchannel is set so JS can receive it
        try:
            self.backend.placeMarker.emit(float(lat), float(lon), 'text')
        except Exception:
            # don't crash UI if emit fails
            pass

        

    def select_photo(self, photo_id):
        self.selecteds_list = list()
        self.selecteds_list.append(photo_id)
        self.selections_display_update()


        for img in self.flickrimgs: 
            if img['id'] == photo_id:
                #self.formwritefields[current_tab_name]['dest_coordinates'].setText(f"{img['latitude']},{img['longitude']}")
                
                lat = img.get('latitude')
                lon = img.get('longitude')
                self.wigets['coords'].setText(f"{lat},{lon}")
                    
    def ShowImageOnMap(self, photo_id):
        self.selecteds_list = list()
        self.selecteds_list.append(photo_id)
        self.selections_display_update()

        for img in self.flickrimgs: 
            if img['id'] == photo_id:
                #self.formwritefields[current_tab_name]['dest_coordinates'].setText(f"{img['latitude']},{img['longitude']}")
                
                lat = img.get('latitude')
                lon = img.get('longitude')
                if lat is not None and lon is not None:
                    self.openlayers_map_refresh(lat,lon)
                #TODO: WRITE HERE
                self.wigets['coords'].setText(f"{lat},{lon}")
                
                if lat is not None and lon is not None:
                    # Emit signal to JS to place marker
                    self.backend.placeMarker.emit(float(lat), float(lon), 'text')
                else:
                    # Clear markers
                    self.backend.clearMarkers.emit()


    def select_photo_append(self, photo_id):
        if photo_id not in self.selecteds_list:
            self.selecteds_list.append(photo_id)
        self.selections_display_update()
    def deselect_photos(self):
        self.selecteds_list=list()
        if len(self.selecteds_list)>0:

            for flickrid in self.selecteds_list:
            
                js = f"decelectImg('{flickrid}');"
                self.browser_main_table.page().runJavaScript(js)
                
        self.selections_display_update()
    def selections_display_update(self):
        if len(self.selecteds_list)>0:
            self.selections_label.setText( '<a href="https://www.flickr.com/photos/organize/?ids='+ ','.join(self.selecteds_list)+'">'+ str(len(self.selecteds_list))+' image(s) '+'</a> ')
            

        else:
            self.selections_label.setText('')
    
if __name__ == "__main__":
    
    

    parser = argparse.ArgumentParser(description="Interface for make photo names of transport on flickr")
    parser.add_argument("--tags", type=str, help="Comma-separated tags for search", required=False)
    
    parser.add_argument("--min_taken_date", type=str, help="Minimum taken date (YYYY-MM-DD HH:MM:SS format)", required='--max_taken_date' in sys.argv or '--interval' in sys.argv)
    parser.add_argument("--max_taken_date", type=str, help="Maximum taken date (YYYY-MM-DD HH:MM:SS format)", required=False)
    parser.add_argument("--days", type=str, help="days to search instead of max-taken-date", required=False)
    parser.add_argument("--per_page", type=int, default=500, help="per page param for flickr search api", required=False)
    parser.add_argument("--exclude", type=str, help="exclude these tags from search. separator is , ") 
    


    args = parser.parse_args()


    app = QApplication(sys.argv)
    window = FlickrBrowser(args)
    window.show()
    sys.exit(app.exec())
