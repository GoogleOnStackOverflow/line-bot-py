# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the 'License'); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
# Google API Key: AIzaSyCgrAXdRBBTzDGjVfyALtpxBuocTZ_6XZ4
from __future__ import unicode_literals

import os
import sys
import googlemaps
import pyrebase
import hashlib
import requests
import jieba
import jieba.posseg as pseg

from argparse import ArgumentParser
from math import radians, cos, sin, asin, sqrt

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)

from linebot.models import *

gmaps = googlemaps.Client(key='AIzaSyCgrAXdRBBTzDGjVfyALtpxBuocTZ_6XZ4')

firebase_config = {
  'apiKey': 'AIzaSyAbFqX4W-2GLUGfPsXPO5oP0cJQdbbqyaM',
  'authDomain': 'line-bot-db.firebaseapp.com',
  'databaseURL': 'https://line-bot-db.firebaseio.com',
  'storageBucket': 'line-bot-db.appspot.com',
  'messagingSenderId': '383008521760'
}

firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'this_should_be_configured')

# get channel_secret and channel_access_token from your environment variable
channel_secret = '209874aceff053b9a2d2858dc201930c'
channel_access_token = 'l97fyfY5AXM7a/PLSAlWl6aoV1kSwUM7+PD2MGTn5cF41TKTiV3Z4tMmc+i/OSZha/n7Pg48r3sCJf+SAEcLMv6TbnvpOM7ErNJKZ/eaJ0bQhBCu8amSY6dVniYzbaIaMT7AmTx3rYGsynm2e/ApTAdB04t89/1O/w1cDnyilFU='
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

# Codes for retrieving data
def distance(lat1, lon1, lat2, lon2):
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    km = 6367 * c
    return km

def get_close_position_data(datatype, lat, lng):
    now_dis = 6367 * 6
    all_data = db.child(datatype).get()
    for data in all_data.each():
        d = distance(lat, lng, (data.val())['lat'], (data.val())['lng'])
        if now_dis > d:
            r = data
            now_dis = d
    return (r.val())['value']

# apixu data
def get_chinese_condition_term(code):
    r = requests.get('http://www.apixu.com/doc/conditions.json')
    for cond in (r.json()):
        if cond['code'] == code:
            r = cond['language']
            break
    for lang in r:
        if lang['lang_iso'] == 'zh_tw':
            return lang

def get_weather_condition(lat,lng):
    r = requests.get('http://api.apixu.com/v1/current.json?key=0c8080a46f27433ea9b191737171101&q='+str(lat)+','+str(lng))
    if not (r.json()).has_key('error'):
        r = r.json()
        current = r['current']
        chinese_term = get_chinese_condition_term(current['condition']['code'])
        if current['is_day'] != 0:
            con_term = chinese_term['day_text']
        else:
            con_term = chinese_term['night_text']
        return {
            'img':'http:' + current['condition']['icon'],
            'con':con_term,
        }
    else:
        return 'unknown'

# Codes for NLP
# Codes for parsing the geo 
not_geo_term = ['天氣','空氣','品質','月','日','年','週','很糟','概況',
    '情形','情況','可能性','機率','降雨','溫度','濕度','濃度','程度','冷','空污','空汙','嚴重','嚴','重',
    '熱','冰','涼','雨','雪','霜','霧','霧霾','霾','霾害','好','附近','空','汙','污','汙染','污染',
    '的','時候','差','壞','糟','話','乾','濕','乾燥','潮濕','高','低','多','用法','會']

em_flag = ['d','p','pa','pbei','c','cc','u','e','y','o','h','k','x','w','qt',
    'qv','r','rr','rz','rzt','rzv','ryt','ryv','rg','t','tg','v','vd','vn','vshi',
    'vyou','vf','vx','vi','vl','vg']

def is_n_keywords(text):
    return (
        text in not_geo_term or
        text.find('點') != -1 or
        text.find('很') != -1 or
        text.find('於') != -1
    )

def gen_to_arr(words):
    t = []
    for word, flag in words:
        t.append({'word':word, 'flag': flag})
    return t

def try_match_geo_name(words):
    t = ''
    for word in words:
        if word['flag'] not in em_flag:
            if not is_n_keywords(word['word']):
                t += word['word'] + ' '
    return t

# Codes for parsing feature type
ask_term = ['問','知道','想','請問','詢問','嗎','有','沒','沒有','?','？','如何','怎樣']
weather_term = ['天氣','空氣','品質','很糟','概況','情形','乾','濕','乾燥','潮濕'
    '情況','可能性','機率','降雨','溫度','濕度','濃度','程度','冷',
    '熱','冰','涼','雨','雪','霜','霧','霧霾','霾','霾害','空','空汙','污染']
reminder_term = ['如果','要是','話','告訴','提醒','通知','時候']
cancel_term = ['不要','取消','不','別','別再']
def feature(words):
    t = 'unknown'
    for word in words:
        if word['word'] == '用法':
            return 'usage'
        if word['word'] in cancel_term:
            return 'c'
        if word['word'] in reminder_term:
            t = 'r'
        if (word['word'] in ask_term or word['word'] in weather_term) and t == 'unknown':
            t ='a'
    return t

def q_type(words):
    for word in words:
        if word['word'] in ['降雨','下雨','淋濕','雨','降水']:
            return 'r'
        if word['word'] in ['溫度','熱','冷','涼','溫暖','暖','冰','凍','度','寒','幾度']:
            return 't'
        if word['word'] in ['濕度','乾','濕','潮濕','乾燥']:
            return 'h'
        if word['word'] in ['空氣','髒','PM','霾害','霧霾','霾','空汙','污染','空']:
            return 'a'
    return 'unknown'

def r_type(words):
    for word in words:
        if word['word'] in ['冷','涼','低','乾','乾燥','冰','凍','寒']:
            return False
    return True

# Codes for generating message
# Location finding Codes
def map_img(addr, lat, lng):
    marker = '&markers=color:blue%7C'+str(lat)+','+str(lng)
    google_api_host = 'https://maps.googleapis.com/maps/api/staticmap?'
    pic_format = 'zoom=16&size=453x300&maptype=roadmap'
    key = '&key=AIzaSyAC1c5MnGfa8VvNjQ9QTJxm7Qvg5wWBOvE'
    return (google_api_host + pic_format + marker + key)

def geo_temp_parser(result):
    lat = result['geometry']['location']['lat']
    lng = result['geometry']['location']['lng']
    addr = result['formatted_address']

    return TemplateSendMessage(
        alt_text='地點確認：請使用手機版以取得最佳體驗',
        template=ButtonsTemplate(
            thumbnail_image_url = map_img(addr, lat, lng),
            title = '這是你要找的地方嗎？',
            text = str(lat) + ' , ' + str(lng),
            actions = [
                PostbackTemplateAction(
                    label = '是',
                    data = str(lat) + ',' + str(lng)
                )
            ]
        )
    )

def geo_loc_parser(result):
    return LocationSendMessage(
        title='搜尋結果',
        address=result['formatted_address'],
        latitude=result['geometry']['location']['lat'],
        longitude=result['geometry']['location']['lng']
    )

def send_loc_data(lat, lng, event, u_event):
    if event == 'unknown' or event == 'r':
        cond = get_weather_condition(lat, lng)
        if cond == 'unknown':
            line_bot_api.push_message(
                u_event.source.sender_id,
                TextSendMessage(text='很抱歉，我找不到該地點的天氣資訊' )
            )
        else:
            line_bot_api.push_message(
                u_event.source.sender_id,
                TemplateSendMessage(
                    alt_text=cond['con'],
                    template=ButtonsTemplate(
                        thumbnail_image_url=cond['img'],
                        title=cond['con'],
                        text='現在氣溫: %s\n濕度：%s%\n' % (get_close_position_data('t',lat, lng), get_close_position_data('h',lat, lng)),
                        actions=[]
                    )
                )
            )
    elif event == 't':
        line_bot_api.push_message(
            u_event.source.sender_id,
            TextSendMessage(text='目前溫度大約是%s度' % get_close_position_data('t',lat, lng))
        )
    elif event == 'h':
        line_bot_api.push_message(
            u_event.source.sender_id,
            TextSendMessage(text='目前濕度大約是%s%' % get_close_position_data('h',lat, lng))
        )
    elif event == 'a':
        line_bot_api.push_message(
            u_event.source.sender_id,
            TextSendMessage(text='目前 PM 2.5 值大約是%s, PSI值則為 %s' % (get_close_position_data('pm25',lat, lng),get_close_position_data('psi',lat, lng)))
        )
    else
        send_cannot_understand(u_event)

def reply_searching(event, location_n):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='正在搜尋\'' + location_n + '\'...')
    )

def send_cannot_understand(event):
    line_bot_api.push_message(
        event.source.sender_id,
        TextSendMessage(text='很抱歉，我不太懂您的意思\n\n您可以問我某地的天氣資料，或是讓我在某地溫濕度過高或過低、降雨機率較高，或是空氣品質不好時提醒您\n詳細使用範例與方法請輸入「用法」')
    )

def send_cannot_find_location(event):
    line_bot_api.push_message(
        event.source.sender_id,
        TextSendMessage(text='很抱歉，我無法找到該地點\n您可以試著用別的詞搜尋\n\n（建議您可以使用地址或較為明顯的地標名稱）' )
    )

def location_checking_flow(event, words):
    location_n = try_match_geo_name(words)
    if location_n != '':
        reply_searching(event, location_n)

        results = gmaps.geocode(location_n)
        if not len(results) == 0:
            line_bot_api.push_message(
                event.source.sender_id,
                geo_loc_parser(results[0])
            )
                        
            line_bot_api.push_message(
                event.source.sender_id,
                geo_temp_parser(results[0])
            )
        else:
            send_cannot_find_location(event)
    else:
        send_cannot_understand(event)

def weather_data_send_flow(event, words):
    location_n = try_match_geo_name(words)
    if location_n != '':
        reply_searching(event, location_n)

        results = gmaps.geocode(location_n)
        if not len(results) == 0:
            line_bot_api.push_message(
                event.source.sender_id,
                geo_loc_parser(results[0])
            )
            
            send_loc_data(results[0]['geometry']['location']['lat'], results[0]['geometry']['location']['lng'], q_type(words), event)
        else:
            send_cannot_find_location(event)
    else:
        send_cannot_understand(event)

@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info('Request body: ' + body)

    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(400)

    # if event is MessageEvent and message is TextMessage, then echo text
    for event in events:
        if isinstance(event , PostbackEvent):
            lat = event.postback.data.split(',')[0]
            lng = event.postback.data.split(',')[1]

            line_bot_api.reply_message(
                event.reply_token,
                loc_data_parser(lat,lng)
            )
            
        elif isinstance(event, MessageEvent):
            if isinstance(event.message, TextMessage):
                words = pseg.cut(event.message.text)
                words = gen_to_arr(words)
                
                f = feature(words)

                if f == 'usage':
                    line_bot_api.push_message(
                    event.source.sender_id,
                    TextSendMessage(text='如果想知道所在位置或特定區域天氣如何，請輸入：某地區（可以小範圍喔！）＋冷（天氣狀況）嗎？\n如果想要開啟通知，請輸入：如果、要是＋某地區＋天氣條件，告訴我！\n如果想要關閉提醒，請輸入：別、不要告訴我＋某地區＋天氣條件了！')
                )
                elif f == 'r':
                    location_checking_flow(event,words)
                elif f == 'a':
                    weather_data_send_flow(event, words)
                else:
                    send_cannot_understand(event)

            elif isinstance(event.message, LocationMessage):
                lat = event.message.latitude
                lng = event.message.longitude
                send_loc_data(lat, lng, 'unknown', event)

    return 'OK'

if __name__ == '__main__':
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug)
