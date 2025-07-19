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
import webbrowser
import argparse
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtGui import QDesktopServices

from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, QUrl

import requests


class Backend(QObject):
    imgSelected = pyqtSignal(str)
    @pyqtSlot(str)
    def handle_select_img(self, image_id):
        self.imgSelected.emit(str(image_id))

    imgSelectedAppend = pyqtSignal(str)
    @pyqtSlot(str)
    def handle_select_img_append(self, image_id):
        self.imgSelectedAppend.emit(str(image_id))        

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
        transport=textsdict['transport'].lower()
        number=str(textsdict.get('number'))
        datestr=info['photo']['dates']['taken'][0:10]
        street=textsdict.get('street')
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
            newname = f'{city} {brand} {model} {numberplate} {datestr} {street} '.replace('  ',' ')

            new_tags=f'"{city}" auto automobile "{street}"'
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
        if desc != '': newdesc = desc + "\n"+street

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
        self.backend.imgSelectedAppend.connect(self.select_photo_append)


        self.init_ui()
        self.flickr = self.authenticate_flickr()
        self.flickrimgs=list()
        
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
        
        #selection panel
        self.selectedimgs_formcontainer=QGroupBox('Selection')
        layout.addWidget(self.selectedimgs_formcontainer)
        self.selectedimgs_formcontainer_layout = QHBoxLayout()
        self.selectedimgs_formcontainer.setLayout(self.selectedimgs_formcontainer_layout)
        self.selections_label=QLabel()
        self.selectedimgs_formcontainer_layout.addWidget(self.selections_label)
        self.deselect_photos_button = QPushButton("Deselect all")
        self.deselect_photos_button.clicked.connect(self.deselect_photos)
        self.selectedimgs_formcontainer_layout.addWidget(self.deselect_photos_button)

        # display browser panel
        self.browser_main_table = QWebEngineView()
        self.browser_main_table.setFixedHeight(450)
        # do not focus on frist href after html set
        self.browser_main_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        #self.browser_main_table.page().settings().setAttribute(QWebEnginePage.WebAttribute.FocusOnNavigationEnabled, False)
        middlelayout.addWidget(self.browser_main_table)
        self.browser_main_table.setHtml('''<html><body><h1>wait for query</h1>''', QUrl("qrc:/"))
       
        # texts form
        self.formtab=QTabWidget()
        middlelayout.addWidget(self.formtab)
        layout.addLayout(middlelayout)
        
        # Create form tabs
        self.routelookup_buttons = {}
        self.geolookup_buttons = {}
        self.numlookup_buttons = {}
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
        self.formtab.setCurrentIndex(1)  # This makes "trolleybus" the default visible tab
        
     
        
        self.changeset_add_btn = QPushButton("Add to changeset")
        self.changeset_add_btn.clicked.connect(self.on_changeset_add)
        layout.addWidget(self.changeset_add_btn)
        
        self.changeset_write_btn = QPushButton("Write changeset")
        self.changeset_write_btn.clicked.connect(self.on_write_changeset)
        layout.addWidget(self.changeset_write_btn)
        
        

        
        self.setLayout(layout)

    def create_tram_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        # Add text fields
        
        for label in ["transport","city","operator","model", "number", "route","street",  'desc', 'more_tags']:
            line_edit = QLineEdit()
            if label=='transport':
                line_edit.setText('tram')
            self.formwritefields['tram'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
            if label=='street':
                self.geolookup_buttons['tram']=dict()
                self.geolookup_buttons['tram']['street']=QPushButton("⇪ geolookup_street ⇪")
                self.geolookup_buttons['tram']['street'].clicked.connect(self.on_geolookup_street)
                form_layout.addRow(":", self.geolookup_buttons['tram']['street'])
            if label=='number':
                self.numlookup_buttons['tram']=dict()
                self.numlookup_buttons['tram']['number']=QPushButton("⇪ take num from name prefix ⇪")
                self.numlookup_buttons['tram']['number'].clicked.connect(self.on_numlookup)
                form_layout.addRow(":", self.numlookup_buttons['tram']['number'])
            if label=='route':
                self.routelookup_buttons['tram']=dict()
                self.routelookup_buttons['tram']['number']=QPushButton("⇪ take route from name prefix ⇪")
                self.routelookup_buttons['tram']['number'].clicked.connect(self.on_routelookup)
                form_layout.addRow(":", self.routelookup_buttons['tram']['number'])
                


        tab.setLayout(form_layout)
        return tab

    def create_trolleybus_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["transport","city","operator", "number", "model","route","street", 'desc',  'more_tags']:
            line_edit = QLineEdit()
            if label=='transport':
                line_edit.setText('trolleybus')
            self.formwritefields['trolleybus'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
        tab.setLayout(form_layout)
        return tab

    def create_bus_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["transport","city","operator", "number","numberplate", "model","route","street",'desc',   'more_tags']:
            line_edit = QLineEdit()
            if label=='transport':
                line_edit.setText('bus')
            self.formwritefields['bus'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
        tab.setLayout(form_layout)
        return tab    

    def create_automobile_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["transport","city","brand", "numberplate", "model","street", 'desc',  'more_tags']:
            line_edit = QLineEdit()
            if label=='transport':
                line_edit.setText('automobile')
            self.formwritefields['automobile'][label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)
        tab.setLayout(form_layout)
        return tab  

    def create_train_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        for label in ["transport","physical","owner","number","station","city","model","line","service", 'desc',  'more_tags']:
            line_edit = QLineEdit()
            if label=='transport':
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
                self.model.transport_image_flickr_update(self.flickr, change['id'], change['textsdict'])
            self.changeset = list()
        else:
            QMessageBox.warning(self, "Invalid data", "Make edits frist")
            
    

        
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
                        text=img['title']

                        
                        import re

                        regex = "_r(.*?)[_.\b]"
                        test_str = text
                        route=''

                        matches = re.finditer(regex, test_str, re.MULTILINE)
                        for match in matches:
                            result = match.group()[2:-1]
                            if "eplace" in result:
                                continue
                            route = result
                            del result
                        if route == "z":
                            route = None
                
                        self.formwritefields[current_tab_name]['route'].setText(route)
                        return
   
                        
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
                        
                        print('signal1')
                        print(request)
                        print(request.status_code)

                        if request.status_code == 201:

                            response = request.json()
                            print(response)



                        self.formwritefields[current_tab_name]['street'].setText(img['latitude']+img['longitude'])
                    
                #self.formwritefields[current_tab_name]['street'].setText('geoliik')
        


    def reset_search_results(self):
        self.browser_main_table.setHtml('''<html><body><h1>wait for query execute</h1>''', QUrl("qrc:/"))
        pass
    
    def search_photos(self):
        #self.get_photos_from_album('72177720327428694')
        #return
        self.reset_search_results()
        trs=''

        params = {"extras": "date_taken,tags,geo,url_o"}
        for key, widget in self.inputs_search.items():
            val = widget.text().strip()
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
            msg=str(photos['photos']['page']).zfill(2) + ' / '+str(photos['photos']['pages']).zfill(2)
            print(msg)
            result_list_page=photos["photos"]["photo"]
            result_list=result_list+result_list_page
            gonextpage=False
            if len(result_list_page)>0 and photos['photos']['pages']>page_counter:
                gonextpage=True
        

        
        self.flickrimgs=list()
        if len(result_list)==0:
            self.info_search_noresults()
        else:
            #result_list = sorted(result_list, key=lambda x: x["datetaken"], reverse=False)
            result_list = sorted(result_list, key=lambda x: float(x["latitude"]), reverse=False)
            for photo in result_list:
                #for photo in sorted(photos["photos"]["photo"], key=lambda d: d['datetaken']):
                if 'namegenerated' in photo['tags']:
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
                    tr.classList.add('selected');
                }
                
                function handleSelectImgAppend(button, imageId) {
                    backend.handle_select_img_append(imageId);
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
        html+=trs
        html+='</table>'
        html+='<p style="font-face: monospace;">Total: '+str(len(result_list))+'</p>'
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
        
        tr=f'''<tr id="{photo['id']}"><td><img src="{image_url}"></td><td>{info}<br/><button  tabindex="-1" onclick="handleSelectImg(this,'{photo['id']}')">Select</button><button tabindex="-1" onclick="handleSelectImgAppend(this,'{photo['id']}')">Append to selection</button></td></tr>'''+"\n"
        return tr


    def select_photo(self, photo_id):
        self.selecteds_list = list()
        self.selecteds_list.append(photo_id)
        self.selections_display_update()

        


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
            self.selections_label.setText(str(len(self.selecteds_list))+': '+' '.join(self.selecteds_list))
            

        else:
            self.selections_label.setText('')
    
if __name__ == "__main__":
    
    

    parser = argparse.ArgumentParser(description="Interface for make photo names of transport on flickr")
    parser.add_argument("--tags", type=str, help="Comma-separated tags for search", required=False)
    
    parser.add_argument("--min_taken_date", type=str, help="Minimum taken date (YYYY-MM-DD HH:MM:SS format)", required='--max_taken_date' in sys.argv or '--interval' in sys.argv)
    parser.add_argument("--max_taken_date", type=str, help="Maximum taken date (YYYY-MM-DD HH:MM:SS format)", required=False)
    parser.add_argument("--days", type=str, help="days to search instead of max-taken-date", required=False)
    parser.add_argument("--per_page", type=int, default=500, help="per page param for flickr search api", required=False)
    


    args = parser.parse_args()


    app = QApplication(sys.argv)
    window = FlickrBrowser(args)
    window.show()
    sys.exit(app.exec())
