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
import jieba
import jieba.posseg as pseg

from argparse import ArgumentParser

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)

from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    LocationMessage, TemplateSendMessage, 
    ButtonsTemplate,
    PostbackTemplateAction, PostbackEvent,
    LocationSendMessage
)

gmaps = googlemaps.Client(key='AIzaSyCgrAXdRBBTzDGjVfyALtpxBuocTZ_6XZ4')

firebase_config = {
  'apiKey': 'AIzaSyAbFqX4W-2GLUGfPsXPO5oP0cJQdbbqyaM',
  'authDomain': 'line-bot-db.firebaseapp.com',
  'databaseURL': 'https://line-bot-db.firebaseio.com',
  'storageBucket': 'line-bot-db.appspot.com'
# 'messagingSenderId': '383008521760'
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

# Codes for NLP
# Codes for parsing the geo 
not_geo_term = ['天氣','空氣','品質','月','日','年','週','很糟','概況',
    '情形','情況','可能性','機率','降雨','溫度','濕度','濃度','程度','冷',
    '熱','冰','涼','雨','雪','霜','霧','霧霾','霾','霾害','好','附近',
    '的','時候','差','壞','糟','話','乾','濕','乾燥','潮濕','高','低']

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
    '熱','冰','涼','雨','雪','霜','霧','霧霾','霾','霾害']
reminder_term = ['如果','要是','話','告訴','提醒','通知','時候']
cancel_term = ['不要','取消']
def feature(words):
    t = 'unknown'
    for word in words:
        if word['word'] in cancel_term:
            return 'c'
        if word['word'] in reminder_term:
            t = 'r'
        if (word['word'] in ask_term or word['word'] in weather_term) and t == 'unknown':
            t ='a'
    return t

def q_type(words):
    for word in words:
        if word['word'] in ['降雨','機率','下雨','淋濕','雨']:
            return 'r'
        if word['word'] in ['溫度','熱','冷']:
            return 't'
        if word['word'] in ['濕度','乾','濕','潮濕','乾燥']:
            return 'h'
        if word['word'] in ['空氣','髒','PM','霾害','霧霾','霾']:
            return 'a'
    return 'unknown'



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

def loc_data_parser(lat, lng):
    return TextSendMessage(
        text='正在取得\n'+ str(lat) + ' , ' + str(lng) + '\n附近的資料...'
    )

def reply_searching(event, location_n):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='正在搜尋\'' + location_n + '\'...')
    )

def send_cannot_understand(event):
    line_bot_api.push_message(
        event.source.sender_id,
        TextSendMessage(text='很抱歉無法辨識您的意思')
    )

def send_cannot_find_location(event):
    line_bot_api.push_message(
        event.source.sender_id,
        TextSendMessage(text='抱歉，無法找到該地點\n您可以試著用別的詞搜尋' )
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
                        
            line_bot_api.push_message(
                event.source.sender_id,
                loc_data_parser(results[0]['geometry']['location']['lat'],results[0]['geometry']['location']['lng'])
            )
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
                if f == 'r' or f == 'a':
                    f += ' :: ' + q_type(words)

                line_bot_api.push_message(
                    event.source.sender_id,
                    TextSendMessage(text=f)
                )

                if f in ['r :: a','r :: t','r :: h','r :: r']:
                    location_checking_flow(event,words)
                elif f in ['a :: a','a :: t','a :: h','a :: r','a :: unknown']:
                    weather_data_send_flow(event, words)
                else:
                    send_cannot_understand(event)

            elif isinstance(event.message, LocationMessage):
                lat = event.message.latitude
                lng = event.message.longitude
                line_bot_api.reply_message(
                    event.reply_token,
                    loc_data_parser(lat, lng)
                )

    return 'OK'


if __name__ == '__main__':
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug)
