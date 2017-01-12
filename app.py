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

def get_close_position_key(datatype, lat, lng):
    now_dis = 6367 * 6
    all_data = db.child(datatype).get()
    for data in all_data.each():
        d = distance(lat, lng, (data.val())['lat'], (data.val())['lng'])
        if now_dis > d:
            r = data
            now_dis = d
    return r.key()

def hum_string(h):
    if h <= 40:
        return '小心灰塵、細菌等容易附著在黏膜上，刺激喉部，引發咳嗽，也會誘發支氣管炎、哮喘等呼吸系統疾病哦！'
    elif h <= 70:
        return '很好的濕度條件！只要保持室內外通風就可以享受美好的時光啦！'
    else:
        return '濕度有點過高了！快打開除溼機讓室內變得舒服，小心在潮濕發黴的環境中，會增加患哮喘和濕疹等過敏性疾病的風險唷。'

def temp_string(t):
    if t <= 10:
        return '寒流來襲，天氣寒冷，出門要穿厚衣服加個厚外套哦！小心不要感冒了！'
    elif t <= 20:
        return '稍有涼意，建議外出加件外套，才不會感冒了唷。'
    elif t <= 30:
        return '溫暖的天氣，可以出外走走，和朋友們一起踏青。'
    else:
        return '炎熱的天氣，記得外出擦個防曬，戴個墨鏡，戴個帽子，多喝水，以免中暑囉！'
def pm_string(t):
    if t <= 35:
        return '空氣好好喔！可以正常戶外活動！'
    elif t <= 53:
        return '空氣有一點點的灰！有心臟、呼吸道及心血管疾病的成人與孩童感受到徵狀時，應考慮減少體力消耗，特別是減少戶外活動哦。'
    elif t <= 70:
        return '空氣品質不太好，出門可以帶個口罩喔！如果有不適，如眼痛，咳嗽或喉嚨痛等，應該考慮減少戶外活動。'
    else:
        return '天呀！空氣太不好了！盡量待在室內，如果有不適要減少戶外活動。有氣喘的人可能需增加使用吸入劑頻率。出門記得做好防護措施哦！'

# apixu data
def get_chinese_condition_term(code):
    r = requests.get('http://www.apixu.com/doc/conditions.json')
    for cond in (r.json()):
        if cond['code'] == code:
            r = cond['languages']
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

def set_reminder(event, lat, lng,qt, rt):
    if qt == 'a':
        line_bot_api.push_message(
            event.source.sender_id,
            TextSendMessage(text='已為您設定 '+str(lat)+','+str(lng)+' 附近的空氣品質提醒')
        )
        nearp = get_close_position_key('pm25', float(lat), float(lng))
        db.child('user').child(str(event.source.sender_id)).child('pm25').update({'type':'pm25','lat':lat,'lng':lng, 'source':nearp , 'value':'True'})
        nearp = get_close_position_key('psi', float(lat), float(lng))
        db.child('user').child(str(event.source.sender_id)).child('psi').update({'type':'psi','lat':lat,'lng':lng, 'source':nearp, 'value':'True'})
    elif not qt == 'unknown':
        if not qt == 'r':
            if qt == 't' :
                tt1 = '溫度'
            else:
                tt1 = '濕度'
            if rt:
                tt1 += '較高時'
            else:
                tt1 += '較低時'

            line_bot_api.push_message(
                event.source.sender_id,
                TextSendMessage(text='已為您設定 '+str(lat)+','+str(lng)+' 附近'+tt1+'的提醒')
            )
            nearp = get_close_position_key(qt, float(lat), float(lng))
            db.child('user').child(str(event.source.sender_id)).child(qt).update({'type':qt,'lat':lat,'lng':lng, 'source':nearp, 'value':str(rt)})
    else:
        line_bot_api.push_message(
            event.source.sender_id,
            TextSendMessage(text='很抱歉，目前提醒功能僅限於提醒溫度、濕度、空氣品質唷' )
        )

def remove_all_reminder(event):
    db.child('user').child(event.source.sender_id).remove()
    line_bot_api.push_message(
        event.source.sender_id,
        TextSendMessage(text='已為您取消所有提醒' )
    )

def get_all_reminder_type(event):
    all_reminder = db.child('user').child(str(event.source.sender_id)).get()
    to_return = []
    for reminder in all_reminder.each():
        to_return.append({
            'type': reminder.key(),
            'data': reminder.val()
        })
    return to_return

# Codes for NLP
# Codes for parsing the geo 
not_geo_term = ['天氣','空氣','品質','月','日','年','週','很糟','概況','冷不冷','熱不熱','不冷','不熱','不'
    '情形','情況','可能性','機率','降雨','溫度','濕度','濃度','程度','冷','空污','空汙','嚴重','嚴','重',
    '熱','冰','涼','雨','雪','霜','霧','霧霾','霾','霾害','好','附近','空','汙','污','汙染','污染',
    '的','時候','差','壞','糟','話','乾','濕','乾燥','潮濕','高','低','多','用法','會','時']

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
weather_term = ['天氣','空氣','品質','很糟','概況','情形','乾','濕','乾燥','潮濕',
    '情況','可能性','機率','降雨','溫度','濕度','濃度','程度','冷','不冷','冷不冷','熱不熱','不熱',
    '熱','冰','涼','雨','雪','霜','霧','霧霾','霾','霾害','空','空汙','污染']
reminder_term = ['如果','要是','話','告訴','提醒','通知','時候','時']
cancel_term = ['不要','取消','別','別再']
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

def geo_temp_parser(result, words):
    lat = result['geometry']['location']['lat']
    lng = result['geometry']['location']['lng']
    addr = result['formatted_address']

    return TemplateSendMessage(
        alt_text='地點確認：請使用手機版以取得最佳體驗',
        template=ButtonsTemplate(
            thumbnail_image_url = map_img(addr, lat, lng),
            title = '這是您要設定提醒的地點嗎？',
            text = str(lat) + ' , ' + str(lng),
            actions = [
                PostbackTemplateAction(
                    label = '是',
                    data = str(lat) + ',' + str(lng) + ',' +str(q_type(words)) + ',' + str(r_type(words))
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
            pm = get_close_position_data('pm25',lat, lng)
            t = cond['con'] + '\n'
            t += '氣溫:'+ str(get_close_position_data('t',lat, lng))+'\n濕度：'+ str(get_close_position_data('h',lat, lng))
            t += '\n空氣品質資料：\nPM 2.5 值為 ' + str(pm) + '\nPSI 值則為 ' + str(get_close_position_data('psi',lat, lng))
            t += '\n' + pm_string(float(pm))

            line_bot_api.push_message(
                u_event.source.sender_id,
                TextSendMessage(text=t)
            )
    elif event == 't':
        val = get_close_position_data('t',lat, lng)
        line_bot_api.push_message(
            u_event.source.sender_id,
            TextSendMessage(text='目前溫度大約是'+str(val)+'度\n' + temp_string(float(val)))
        )
    elif event == 'h':
        val = get_close_position_data('h',lat, lng)
        line_bot_api.push_message(
            u_event.source.sender_id,
            TextSendMessage(text='目前濕度大約是' + str(val) + '%\n' + hum_string(float(val)))
        )
    elif event == 'a':
        pm = get_close_position_data('pm25',lat, lng)
        line_bot_api.push_message(
            u_event.source.sender_id,
            TextSendMessage(text='目前 PM 2.5 值大約是 ' + str(pm) + '\nPSI 值則為 ' + str(get_close_position_data('psi',lat, lng)) +'\n'+ pm_string(float(pm)))
        )
    else:
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
                geo_temp_parser(results[0], words)
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

def send_user_all_remind(event):
    users = db.child('user').get()
    if users.val().has_key(event.source.user_id):
        reminds = db.child('user').child(event.source.user_id).get()
        line_bot_api.push_message(
            event.source.sender_id,
            TextSendMessage(text='您所設定的提醒如下' )
        )
        for remind in reminds.each():
            remind = remind.val()
            qt = remind['type']
            if qt == 't' :
                tt1 = '溫度'
            elif qt == 'h':
                tt1 = '濕度'
            elif qt == 'pm25':
                tt1 = 'PM 2.5值'
            elif qt == 'psi':
                tt1 = 'PSI值'
            rt = remind['value']
            if rt == 'True':
                tt1 += '較高時'
            else:
                tt1 += '較低時'
            line_bot_api.push_message(
                event.source.sender_id,
                LocationSendMessage(
                    title=tt1+'的提醒',
                    address=str(round(float(remind['lat']),6))+','+str(round(float(remind['lng']),6))+'\n附近',
                    latitude=float(remind['lat']),
                    longitude=float(remind['lng'])
                )
            )
        line_bot_api.push_message(
            event.source.sender_id,
            TextSendMessage(text='您可以告訴我取消、不要提醒，我就會幫您取消所有提醒囉')
        )
    else:
        line_bot_api.push_message(
            event.source.sender_id,
            TextSendMessage(text='您尚未設定任何提醒\n您可以告訴我：當...的時候提醒我，例如：\n如果台北市大安區空氣不好的話通知我' )
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
            lat = event.postback.data.split(',')[0]
            lng = event.postback.data.split(',')[1]
            qt = event.postback.data.split(',')[2]
            rt = event.postback.data.split(',')[3]
            if rt == 'True':
                rt = True
            else:
                rt = False

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='正在為您設定')
            )
            set_reminder(event, lat, lng, qt, rt)
            
        elif isinstance(event, MessageEvent):
            if isinstance(event.message, TextMessage):
                words = pseg.cut(event.message.text)
                words = gen_to_arr(words)
                
                f = feature(words)
                if event.message.text == '我的提醒':
                    send_user_all_remind(event)
                elif f == 'usage':
                    line_bot_api.push_message(
                        event.source.sender_id,
                        TextSendMessage(text='如果想知道所在位置或特定區域天氣如何，您可以問我：某地區（可以小範圍喔！）＋冷（天氣狀況）嗎？\n如果想要開啟通知，您可以告訴我：如果、要是＋某地區＋天氣條件 的時候告訴我！\n想要看有些已設定的通知，請告訴我「我的通知」\n如果想要關閉提醒，您可以告訴我：取消提醒')
                    )
                elif f == 'r':
                    location_checking_flow(event,words)
                elif f == 'a':
                    weather_data_send_flow(event, words)
                elif f == 'c':
                    remove_all_reminder(event)
                else:
                    send_cannot_understand(event)

            elif isinstance(event.message, LocationMessage):
                lat = event.message.latitude
                lng = event.message.longitude
                send_loc_data(lat, lng, 'unknown', event)

    return 'OK'

@app.route('/reminder/<reminding>', methods=['POST'])
def reminder(reminding):
    user_id = reminding.split('/')[0]
    qtype = reminding.split('/')[1]
    data_point = reminding.split('/')[2]

    rest = db.child(qtype).child(data_point).get()
    lat = (rest.val())['lat']
    lng = (rest.val())['lng']
    data_val = (rest.val())['value']
    if qtype == 't':
        tt1 = '溫度'
    elif qtype == 'h':
        tt1 = '濕度'
    elif qtype == 'pm25':
        tt1 = ' PM2.5 值'
    elif qtype == 'psi':
        tt1 = ' PSI 值'

    line_bot_api.push_message(
        user_id,
        TextSendMessage(text='提醒您，目前 '+str(lat)+','+str(lng)+' 附近的'+tt1+'為 '+data_val)
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
