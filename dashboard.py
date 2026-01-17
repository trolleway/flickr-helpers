import flickrapi
import config

import os

class Processor():
    def __init__(self):
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
    
    def images_list_to_visual(self,images):
        text=''
        sdict={0:'-',1:'+',None:'x'}
        for image in images:
            text = text + sdict(image.get('mark',None))
            
        return text
    
    def info_search_noresults(self):
        print('no result')
    def dashboard_namegenerated(self,date:str,days:int=1):
        params = {"extras": "date_taken,tags,geo,url_o,url_k"}
        
        raw_date = date
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    date = datetime.strptime(raw_date, fmt)
                    break
                except ValueError:
                    continue
        params["min_taken_date"] = date
        next_day = date + timedelta(days=int(days))
        params["max_taken_date"] = next_day.strftime("%Y-%m-%d %H:%M:%S")
        params["user_id"] = self.flickr.test.login()['user']['id']
        params['sort']='date-taken-asc'
        params['per_page']=500
        params['content_types']='0'
        photos = self.flickr.photos.search(**params)
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
        

        files_to_display = 0
        if len(result_list)==0:
            
            self.info_search_noresults()
        else:
            SORTMODE = 'datetaken'
            if SORTMODE == 'datetaken':
                result_list = sorted(result_list, key=lambda x: x["datetaken"], reverse=False)
            elif SORTMODE == 'lon':
                result_list = sorted(result_list, key=lambda x: float(x["longitude"]), reverse=False)
            elif SORTMODE == 'lat':
                result_list = sorted(result_list, key=lambda x: float(x["latitude"]), reverse=True)
            elif SORTMODE == 'title':
                result_list = sorted(result_list, key=lambda x: x["title"], reverse=False)
            else:
                result_list = sorted(result_list, key=lambda x: x["datetaken"], reverse=False)
        
        images_list_output = list()
        for photo in result_list:
                
            # filtering 
            if ('namegenerated' in photo['tags'] and skip_if_namegenerated) and 'noname' not in photo['tags']:
                continue
            if ('duplicate' in photo['tags'] and skip_if_namegenerated) and 'noname' not in photo['tags']:
                continue
            if ('nonpublic' in photo['tags'] and skip_if_namegenerated) and 'noname' not in photo['tags']:
                continue                    
            if self.filters_checkbox_has_dest.isChecked():
                if photo['id'] not in self.dest_point_by_flickrid:
                    continue
            if self.filters_checkbox_no_dest.isChecked():
                if photo['id'] in self.dest_point_by_flickrid:
                    continue
                
            if 'namegenerated' in photo['tags']:
                photo['mark']=1
            else:
                photo['mark']=0
            images_list_output.append(photo)