import os
from dotenv import load_dotenv

load_dotenv()
class Config:
    # Flask app config
    
    # MySQL connection config
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'  # Change to your database username
    MYSQL_DB = 'blood_bank_db'
    MYSQL_CURSORCLASS = 'DictCursor'

