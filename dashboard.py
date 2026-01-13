import sys
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel)
from PyQt6.QtWebEngineWidgets import QWebEngineView
import flickrapi
import config

# Replace these with your actual Flickr API Key and Secret
# Get them from: https://www.flickr.com/services/api/keys/


class FlickrApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flickr Private Photo Viewer (2026)")
        self.resize(1000, 700)

        # Initialize Flickr API
        # flickrapi handles OAuth; it will open a browser for first-time auth
        self.flickr = flickrapi.FlickrAPI(config.API_KEY, config.API_SECRET, format='parsed-json')
        self.flickr.authenticate_via_browser(perms='write')

        # UI Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Control Panel
        controls = QHBoxLayout()
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("YYYY-MM-DD")
        self.date_input.setText(datetime.now().strftime("%Y-%m-%d"))
        
        self.search_btn = QPushButton("Display images")
        self.search_btn.clicked.connect(self.load_photos)
        
        controls.addWidget(QLabel("Date Taken:"))
        controls.addWidget(self.date_input)
        controls.addWidget(self.search_btn)
        layout.addLayout(controls)

        # WebEngine View for HTML Output
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

    def load_photos(self):
        date_str = self.date_input.text()
        try:
            # Prepare date range for the specific day
            start_dt = datetime.strptime(date_str, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=1)
            
            # Format dates for Flickr (MySQL datetime format)
            # Reference: 
            
            min_taken = start_dt.strftime('%Y-%m-%d 00:00:00')
            max_taken = end_dt.strftime('%Y-%m-%d 00:00:00')

            # Search calling user's photos (user_id='me' requires auth)
            # Including private photos via authentication
            response = self.flickr.photos.search(
                user_id='me',
                min_taken_date=min_taken,
                max_taken_date=max_taken,
                extras='url_s,date_taken,tags,geo'
            )

            photos = response.get('photos', {}).get('photo', [])
            self.display_html_namegenerated(photos, date_str)

        except ValueError:
            self.web_view.setHtml("<h3>Error: Invalid date format. Use YYYY-MM-DD.</h3>")
        except Exception as e:
            self.web_view.setHtml(f"<h3>API Error: {str(e)}</h3>")

    def display_html_thumbs(self, photos, date_str):
        if not photos:
            html = f"<h3>No photos found for {date_str}</h3>"
        else:
            html = f"<h2>Photos taken on {date_str}</h2><ul style='list-style:none;'>"
            for p in photos:
                img_url = p.get('url_s', '') # Small image URL
                title = p.get('title', 'Untitled')
                taken = p.get('datetaken', '')
                html += f"""
                <li style='margin-bottom: 20px; border-bottom: 1px solid #ccc; padding-bottom: 10px;'>
                    <img src='{img_url}' style='max-width: 240px; display: block;' />
                    <strong>{title}</strong><br/>
                    <small>Taken: {taken}</small>
                </li>
                """
            html += "</ul>"
        
        self.web_view.setHtml(html)

    def display_html_namegenerated(self, photos, date_str):
        if not photos:
            html = f"<h3>No photos found for {date_str}</h3>"
        else:
            html = f"<h2>Photos taken on {date_str}</h2><table>"
            for p in photos:
                img_url = p.get('url_s', '') # Small image URL
                title = p.get('title', 'Untitled')
                namegenerated='namegenerated' in p.get('tags','')
                if namegenerated == True:
                    marknamegenerated='✅'
                else:
                    marknamegenerated='❌'
                if p.get('latitude'):
                    markgeo='✅'
                else:
                    markgeo='❌'
                taken = p.get('datetaken', '')
                html += f"<tr><td>{title}</td><td>{marknamegenerated}</td><td>{markgeo}</td></tr>"
                '''
                html += f"""
                <li style='margin-bottom: 20px; border-bottom: 1px solid #ccc; padding-bottom: 10px;'>
                    <img src='{img_url}' style='max-width: 240px; display: block;' />
                    <strong>{title} {namegenerated}</strong><br/>
                    <small>Taken: {taken}</small>
                </li>
                """
                '''
            html += "</table>"
        
        self.web_view.setHtml(html)
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlickrApp()
    window.show()
    sys.exit(app.exec())
