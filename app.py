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

def text_m_analyzer(text):
    words = pseg.cut(text)
    t = ''
    for word, flag in words:
        t += (word + ' :: ' + flag + '\n')
    return TextSendMessage(text=t)

def map_img(addr, lat, lng):
    addr_t = addr.replace(' ', '+')
    marker = '&markers=color:blue%7C'+str(lat)+','+str(lng)
    google_api_host = 'https://maps.googleapis.com/maps/api/staticmap?center='
    pic_format = '&zoom=16&size=453x300&maptype=roadmap'
    key = '&key=AIzaSyAC1c5MnGfa8VvNjQ9QTJxm7Qvg5wWBOvE'
    return (google_api_host + addr_t + pic_format + marker + key)

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
            print event.postback.data
            lat = event.postback.data.split(',')[0]
            lng = event.postback.data.split(',')[1]

            line_bot_api.reply_message(
                event.reply_token,
                loc_data_parser(lat,lng)
            )

        elif isinstance(event, MessageEvent):
            if isinstance(event.message, TextMessage):
                print event.source.sender_id
                line_bot_api.reply_message(
                    event.reply_token,
                    #TextSendMessage(text='正在搜尋\'' + event.message.text + '\'...')
                    text_m_analyzer(event.message.text)
                )

                results = gmaps.geocode(event.message.text)
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
                    line_bot_api.push_message(
                        event.source.sender_id,
                        TextSendMessage(text='抱歉，無法找到該地點\n你可以試著用別的詞搜尋看看哦' )
                    )

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
