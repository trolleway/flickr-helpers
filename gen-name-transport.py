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

class ImageLoaderSignals(QObject):
    finished = pyqtSignal(QPixmap, object, str)  # pixmap, photo, error_text

class ImageLoader(QRunnable):
    def __init__(self, image_url, photo, callback):
        super().__init__()
        self.image_url = image_url
        self.photo = photo
        self.signals = ImageLoaderSignals()
        self.signals.finished.connect(callback)

    def run(self):
        pixmap = QPixmap()
        error_text = ""
        try:
            data = urlopen(self.image_url).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
        except HTTPError as e:
            error_text = f"HTTP Error {e.code}"
        except URLError as e:
            error_text = f"URL Error: {e.reason}"
        except Exception as e:
            error_text = f"Unexpected error: {str(e)}"
        self.signals.finished.emit(pixmap, self.photo, error_text)
        
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

        city=textsdict['city'].capitalize()
        transport=textsdict['transport'].lower()
        number=str(textsdict['number'])
        datestr=info['photo']['dates']['taken'][0:10]
        street=textsdict['street']
        model=textsdict.get('model')
        route=str(textsdict.get('route'))
        newname = f'{city} {transport} {number} {datestr} {street} {model}'.replace('  ',' ')

        new_tags=f'"{city}" {transport} "{street}"'
        if route is not None and len(route)>0:
            new_tags += ' line'+str(route)
        if model is not None and len(model)>0:
            if ' ' in model:
                new_tags += ' "'+str(model)+'"'
            else:    
                new_tags += ' '+str(model)
        operator = textsdict.get('operator','')
        operator = str(operator)
        operator=operator.strip()
        
        if operator != '':
            new_tags += ' '+str(operator)
        more_tags = list()    
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
        


        self.init_ui()
        self.flickr = self.authenticate_flickr()

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
        self.inputs_search["per_page"].setText(str(50))
        self.inputs_search["days"].setInputMask("00") 
        #self.inputs_search["days"].setPlaceholderText("number")
        #self.inputs_search["page"].setPlaceholderText("1")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_photos)
        layout.addWidget(self.search_btn)
        
        # Image scroll area
        self.selectarea=QHBoxLayout()
        self.scroll_area = QScrollArea()
        
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(400)
        #self.scroll_area.setMinimumHeight(400)
        self.scroll_area.setMaximumHeight(412)
        #self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_widget)

        
        self.selectarea.addWidget(self.scroll_area, stretch=1)
        
        
        #browser
        self.browser = QWebEngineView()
        #self.browser.setMaximumHeight(400)
        self.browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.selectarea.addWidget(self.browser, stretch=0)
        self.browser.setHtml('''<html><body>content</body></html> ''')
        
        
        layout.addLayout(self.selectarea)
        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
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
        
        
        # texts form
        self.formtab=QTabWidget()
        layout.addWidget(self.formtab)
        
        # Create form tabs
        self.formtab.addTab(self.create_tram_tab(), "tram")
        #self.formtab.addTab(self.create_trolleybus_tab(), "trolleybus")
        self.formtab.addTab(QWidget(), "bus")   # Empty tab
        self.formtab.setCurrentIndex(1)  # This makes "trolleybus" the default visible tab
        
        # Add "write" button
        self.write_btn = QPushButton("Write")
        self.write_btn.clicked.connect(self.on_write)
        layout.addWidget(self.write_btn)
        
        self.setLayout(layout)

    def create_tram_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        # Add text fields
        self.fields = {}
        for label in ["transport","operator","city","model", "number", "route","street",   'more_tags']:
            line_edit = QLineEdit()
            if label=='transport':
                line_edit.setText('tram')
            self.fields[label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)


        tab.setLayout(form_layout)
        return tab

    def create_trolleybus_tab(self):
        tab = QWidget()
        form_layout = QFormLayout()

        # Add text fields
        self.fields = {}
        for label in ["transport","street", "model", "number", "route", "city", "operator"]:
            line_edit = QLineEdit()
            if label=='transport':
                line_edit.setText('trolleybus')
            self.fields[label] = line_edit
            form_layout.addRow(label.capitalize() + ":", line_edit)



        tab.setLayout(form_layout)
        return tab
    
    def display_image_browser(self, url):
        html = f"""
        <html>
        <body style="margin:0; padding:0; display:flex; justify-content:center; align-items:center; height:100vh; background-color:#f0f0f0;">
            <img src="{url}" alt="Image" style="max-width:100%; max-height:100%;" />
        </body>
        </html>
        """
        self.browser.setHtml(html)
        
    def on_write(self):
        self.write_btn.setText('...writing...')
        self.write_btn.setEnabled(False)
        textsdict = {field: widget.text() for field, widget in self.fields.items()}
        flickrid=''
        if len(self.selecteds_list)>0:
            for flickrid in self.selecteds_list:
                self.model.transport_image_flickr_update(self.flickr, flickrid, textsdict)
        else:
            QMessageBox.warning(self, "Invalid data", "Select photo frist")
        
        self.deselect_photos()
        self.write_btn.setText('Write')
        self.write_btn.setEnabled(True)
        
        
        


    def reset_search_results(self):
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)      
    def search_photos(self):
        #self.get_photos_from_album('72177720327428694')
        #return
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
        params['per_page']=int(params['per_page'])
        #params['page'] = 1

        #params['page']=1
        photos = self.flickr.photos.search(**params)
        #result_list=photos["photos"]["photo"]
        
        result_list = list()
        gonextpage=True
        page_counter=0
        while(gonextpage):
            page_counter = page_counter+1
            params['page']=page_counter
            print(params)
            photos = self.flickr.photos.search(**params)
            result_list_page=photos["photos"]["photo"]
            result_list=result_list+result_list_page
            gonextpage=False
            if len(result_list_page)>0 and photos['photos']['pages']>page_counter:
                gonextpage=True
        


        
        if len(result_list)==0:
            self.info_search_noresults()
        else:
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


                self.add_photo_widget(photo)
        pass


    def info_search_noresults(self):
        QMessageBox.warning(self, "Not found", "Select photo return no results")
    def add_photo_widget(self, photo):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        vbox = QHBoxLayout()
        frame.setLayout(vbox)

        #image_url = photo.get("url_w")
        image_url = f"https://live.staticflickr.com/{photo['server']}/{photo['id']}_{photo['secret']}_w.jpg"
        if image_url:
            label = QLabel("Loading...")
            
            '''
            try:
                data = urlopen(image_url).read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                label = QLabel()
                label.setPixmap(pixmap)
            except:
                label = QLabel()
                label.setText('some error')
            '''
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(label)
            def on_image_loaded(pixmap, photo, error_text):
                if not pixmap.isNull():
                    label.setPixmap(pixmap)
                else:
                    label.setText(error_text or "some error")

        loader = ImageLoader(image_url, photo, on_image_loaded)
        QThreadPool.globalInstance().start(loader)

        geo_text=''
        if photo['latitude']==0: 
            geo_text='🌍❌'
            
        photo_url = f"https://www.flickr.com/photos/{photo['owner']}/{photo['id']}/in/datetaken/"
        info = QLabel(f"{photo['title']}{geo_text} {photo['datetaken']} <br><a href='{photo_url}'>Open on Flickr</a>")
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        info.setOpenExternalLinks(True)
        vbox.addWidget(info)


        select_button = QPushButton("Select Only This Photo")
        select_button.clicked.connect(lambda _, pid=photo['id']: self.select_photo(pid,image_url))
        vbox.addWidget(select_button)

        select_button_append = QPushButton("Multiple selection")
        select_button_append.clicked.connect(lambda _, pid=photo['id']: self.select_photo_append(pid))
        vbox.addWidget(select_button_append)
        self.scroll_layout.addWidget(frame)

    def select_photo(self, photo_id,image_url):
        self.selecteds_list = list()
        self.selecteds_list.append(photo_id)
        self.selections_display_update()
        self.display_image_browser(image_url)
        


    def select_photo_append(self, photo_id):
        if photo_id not in self.selecteds_list:
            self.selecteds_list.append(photo_id)
        self.selections_display_update()
    def deselect_photos(self):
        self.selecteds_list=list()
        self.selections_display_update()
    def selections_display_update(self):
        if len(self.selecteds_list)>0:
            self.selections_label.setText(str(len(self.selecteds_list))+': '+' '.join(self.selecteds_list))
            self.write_btn.setEnabled(True)
            #for flickrid in self.selecteds_list:
            #    self.selections_label
        else:
            self.selections_label.setText('')
            self.write_btn.setEnabled(False)
    
if __name__ == "__main__":
    
    

    parser = argparse.ArgumentParser(description="Interface for make photo names of transport on flickr")
    parser.add_argument("--tags", type=str, help="Comma-separated tags for search", required=False)
    
    parser.add_argument("--min_taken_date", type=str, help="Minimum taken date (YYYY-MM-DD HH:MM:SS format)", required='--max_taken_date' in sys.argv or '--interval' in sys.argv)
    parser.add_argument("--max_taken_date", type=str, help="Maximum taken date (YYYY-MM-DD HH:MM:SS format)", required=False)
    parser.add_argument("--days", type=str, help="days to search instead of max-taken-date", required=False)
    parser.add_argument("--per_page", type=str, help="per page param for flickr search api", required=False)
    


    args = parser.parse_args()


    app = QApplication(sys.argv)
    window = FlickrBrowser(args)
    window.show()
    sys.exit(app.exec())
