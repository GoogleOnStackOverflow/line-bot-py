import os
import sys
import hashlib
import threading
import requests
import pyrebase

firebase_config = {
  'apiKey': 'AIzaSyAbFqX4W-2GLUGfPsXPO5oP0cJQdbbqyaM',
  'authDomain': 'line-bot-db.firebaseapp.com',
  'databaseURL': 'https://line-bot-db.firebaseio.com',
  'storageBucket': 'line-bot-db.appspot.com',
  'messagingSenderId': '383008521760'
}

firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()

# Codes for retrieving data
def db_data_obj(datatype, lat, lng, value, source, time):
    return {'datatype':datatype, 'data':{'lat':lat, 'lng':lng, 'value':value, 'source':source, 'time':time}}

def parse_api_data_one(data, source):
    if source == 'LASS' or source == 'AIRBOX':
        return [
            db_data_obj('t', data['gps_lat'], data['gps_lon'], data['s_t0'], source, data['timestamp']),
            db_data_obj('h', data['gps_lat'], data['gps_lon'], data['s_h0'], source, data['timestamp']),
            db_data_obj('pm25', data['gps_lat'], data['gps_lon'], data['s_d0'], source, data['timestamp'])
        ]
    elif source == 'EPA':
        return [
            db_data_obj('pm25', data['gps_lat'], data['gps_lon'], data['PM2_5'], source, data['timestamp']),
            db_data_obj('psi', data['gps_lat'], data['gps_lon'], data['PSI'], source, data['timestamp'])
        ]

def parse_api_data(arr, source):
    r = []
    for data in arr:
        r += parse_api_data_one(data, source)
    return r

def geo_child_name(lat, lng):
    sha_1 = hashlib.sha1()
    sha_1.update(str(lat)+','+str(lng))
    return sha_1.hexdigest()
    

def update_db(arr):
    for data in arr:
        db.child(data['datatype']).child(geo_child_name(data['data']['lat'],data['data']['lng'])).set({
            'lat':data['data']['lat'],
            'lng':data['data']['lng'],
            'value':data['data']['value'],
            'source':data['data']['source'],
            'time':data['data']['time']
        })

def renew_api_data(url, source):
    print('Retrieving data from API: ' + url)
    r = requests.get(url)
    if r.status_code == 200 or r.status_code == '200':
        arr_to_parse = (r.json())['feeds']
        if arr_to_parse:
            arr_to_parse = parse_api_data(arr_to_parse, source)
            update_db(arr_to_parse)

def renew_db():
    threading.Timer(300.0, renew_db).start() # called every five minutes
    print('renewing db')
    #threading.Timer(300.0, renew_db).start() # called every five minutes
    renew_api_data('http://nrl.iis.sinica.edu.tw/LASS/last-all-lass.json', 'LASS')
    renew_api_data('http://nrl.iis.sinica.edu.tw/LASS/last-all-epa.json', 'EPA')
    renew_api_data('http://nrl.iis.sinica.edu.tw/LASS/last-all-airbox.json', 'AIRBOX')

if __name__ == '__main__':
    renew_db()