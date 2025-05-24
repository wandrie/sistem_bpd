import os

# Konfigurasi Umum
SECRET_KEY = os.urandom(24) 
DEBUG = True 
PORT = 5000  

# Konfigurasi Database 
MYSQL_HOST = 'localhost'
MYSQL_USER = 'root'
MYSQL_PASSWORD = ''
MYSQL_DB = 'sistem_bpd'
MYSQL_PORT = 3306
MYSQL_CURSORCLASS = 'DictCursor'

# Konfigurasi Upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
