from flask import Flask, request, abort
from settings import CHANNEL_ACCESS_TOKEN, CHANNEL_SECRET, GOOGLE_API_KEY
import requests
import pickle
import folium
import geocoder
import numpy as np
import pandas as pd

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, VideoMessage, AudioMessage, LocationMessage, TextSendMessage,
)

app = Flask(__name__)

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


@app.route("/", methods=['GET','POST'])
def index():
    with open("cbike.pickle","rb") as f_pkl:
        df = pickle.load(f_pkl)
    center = [22.6272784, 120.3014353] # Kaohsiung Center
    map = folium.Map(location=center, zoom_start=14)

    for index, row in df.iterrows():
        folium.Marker(
            location=(row['lat'], row['lon']),
            popup="<div style='white-space:nowrap'>{}</div>".format(row['name']),
            icon=folium.Icon(icon='bicycle',prefix='fa')
        ).add_to(map)

    return map._repr_html_()


@app.route('/<address>')
def center(address):
    with open("cbike.pickle","rb") as f_pkl:
        df = pickle.load(f_pkl)

    try:
        center = geocoder.google(address, key=GOOGLE_API_KEY).latlng
        map = folium.Map(location=center, zoom_start=16)
    except:
        center = [22.6272784, 120.3014353] # Taiwan Center
        map = folium.Map(location=center, zoom_start=14)

    folium.Marker(
            location=center,
            popup="<div style='white-space:nowrap'>{}</div>".format(address),
            icon=folium.Icon(color='red')
        ).add_to(map)

    for index, row in df.iterrows():
        folium.Marker(
            location=(row['lat'], row['lon']),
            popup="<div style='white-space:nowrap'>{}</div>".format(row['name']),
            icon=folium.Icon(icon='bicycle', prefix='fa')
        ).add_to(map)
    
    return map._repr_html_()


@app.route('/latlon/<lat>/<lon>')
def gps(lat, lon):
    with open("cbike.pickle","rb") as f_pkl:
        df = pickle.load(f_pkl)

    try:
        center = [float(lat), float(lon)]
        map = folium.Map(location=center, zoom_start=16)
    except:
        center = [22.6272784, 120.3014353] # Kaohsiung Center
        map = folium.Map(location=center, zoom_start=14)

    folium.Marker(
            location=center,
            popup="<div style='white-space:nowrap'>GPS: ({},{})</div>".format(lat, lon),
            icon=folium.Icon(color='red')
        ).add_to(map)

    for index, row in df.iterrows():
        folium.Marker(
            location=(row['lat'], row['lon']),
            popup="<div style='white-space:nowrap'>{}</div>".format(row['name']),
            icon=folium.Icon(icon='bicycle',prefix='fa')
        ).add_to(map)

    return map._repr_html_()


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    print("Receive a text message!")
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text))


def haversine(lat1, lon1, lat2, lon2, to_radians=True, earth_radius=6371):
    """
    slightly modified version: of http://stackoverflow.com/a/29546836/2901002

    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees or in radians)

    All (lat, lon) coordinates must have numeric dtypes and be of equal length.

    """
    if to_radians:
        lat1, lon1, lat2, lon2 = np.radians([lat1, lon1, lat2, lon2])

    a = np.sin((lat2-lat1)/2.0)**2 + \
        np.cos(lat1) * np.cos(lat2) * np.sin((lon2-lon1)/2.0)**2

    return earth_radius * 2 * np.arcsin(np.sqrt(a))


def location(address):
    return geocoder.google(address, key=GOOGLE_API_KEY).latlng


@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    m = event.message
    address = "名稱: {}\n地址: {}\n緯度: {}\n經度: {}\n".format(m.title,m.address,m.latitude,m.longitude)
    
    # 擷取附近的腳踏車站資訊
    with open("cbike.pickle","rb") as f_pkl:
        df = pickle.load(f_pkl)

    lat, lon = m.latitude, m.longitude
    lats = np.ones(len(df)) * lat
    lons = np.ones(len(df)) * lon
    df['距離(m)'] = 1000*haversine(lats, lons, df['lat'], df['lon'])
    df_closest = df.sort_values('距離(m)', ascending=True)[['name','address','距離(m)']]

    c = 0
    text = "最近三個腳踏車站如下：\n\n"
    for index, row in df_closest.iterrows():
        text += "站名：" + row['name'] + "\n"
        text += "距離(m)：" + str(row['距離(m)']) + "\n"
        text += "地址：" + row['address'] + "\n\n"
        if c > 1:
            break
        else:
            c += 1

    text += "檢視地圖：https://cbike.herokuapp.com/latlon/{0}/{1}?openExternalBrowser=1".format(m.latitude, m.longitude)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=address+"\n"+text))


if __name__ == "__main__":
    #app.run(debug=True)
    app.run()