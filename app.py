from flask import Flask, jsonify, request
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import ssl
import os
from dotenv import load_dotenv
from datetime import datetime

# .env 파일에서 환경 변수 로드
load_dotenv()

# Flask 앱 초기화
app = Flask(__name__)

# 한국관광공사 API 정보
API_KEY = os.getenv("API_KEY")
BASE_URL = "https://apis.data.go.kr/B551011/KorService1"

print(f"Loaded API Key: {API_KEY}")
if not API_KEY:
    print("API_KEY가 로드되지 않았습니다.")
    exit(1)

class SSLAdapter(HTTPAdapter):
    """ SSL/TLS 버전을 낮춰 호환성을 확보하는 어댑터 """
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

def call_api(endpoint, params):
    url = f"{BASE_URL}/{endpoint}"
    params["serviceKey"] = API_KEY
    params["MobileOS"] = "AND"
    params["MobileApp"] = "MyApp"
    params["_type"] = "json"

    print("Request URL:", url)
    print("Request Params:", params)

    session = requests.session()
    session.mount("https://", SSLAdapter())

    try:
        response = session.get(url, params=params, timeout=20)
        response.raise_for_status()

        print("Response Status Code:", response.status_code)
        print("Response Text:", response.text)

        data = response.json()
        
        # HTTP를 HTTPS로 변환
        if 'items' in data['response']['body']:
            for item in data['response']['body']['items']['item']:
                if 'firstimage' in item and item['firstimage'].startswith("http://"):
                    item['firstimage'] = item['firstimage'].replace("http://", "https://")
                if 'firstimage2' in item and item['firstimage2'].startswith("http://"):
                    item['firstimage2'] = item['firstimage2'].replace("http://", "https://")
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"API 호출 오류: {e}")
        return {"error": str(e)}
    except ValueError as e:
        print("JSON 변환 오류:", e)
        return {"error": "Invalid JSON response"}

# 1. 행사정보조회 API
@app.route('/api/festivals', methods=['GET'])
def get_festivals():
    event_start_date = request.args.get('eventStartDate')
    area_code = request.args.get('areaCode')
    page = int(request.args.get('page', 1))  # 페이지 번호, 기본값은 1
    page_size = int(request.args.get('pageSize', 10))  # 한 페이지의 아이템 수, 기본값은 10

    # 현재 날짜 가져오기
    current_date = datetime.now()
    current_year = current_date.strftime("%Y")
    current_month = current_date.strftime("%m")
    current_ym = current_date.strftime("%Y%m")

    # eventStartDate가 주어지지 않으면 현재 연도로 설정
    if not event_start_date:
        event_start_date = current_year + "0101"

    event_end_date = current_year + "1231"

    params = {
        "eventStartDate": event_start_date,
        "eventEndDate": event_end_date,
        "pageNo": page,
        "numOfRows": page_size,
        "MobileOS": "AND",
        "MobileApp": "MyApp",
        "_type": "json"
    }

    if area_code:
        params["areaCode"] = area_code

    data = call_api("searchFestival1", params)

    # 데이터가 없을 경우 바로 반환
    if "response" not in data or "body" not in data["response"]:
        return jsonify(data)

    festivals = data["response"]["body"].get("items", {}).get("item", [])
    unique_festivals = {festival['contentid']: festival for festival in festivals}.values()

    # 축제 데이터가 유효한지 확인하고 정렬
    current_month_festivals = []
    upcoming_festivals = []
    past_festivals = []

    for festival in festivals:
        start_date = festival.get("eventstartdate")
        if start_date and len(start_date) == 8:
            festival_date = datetime.strptime(start_date, "%Y%m%d")
            
            # 현재 달의 축제
            if festival_date.strftime("%Y%m") == current_ym:
                current_month_festivals.append(festival)
            elif festival_date > current_date:
                upcoming_festivals.append(festival)
            else:
                past_festivals.append(festival)

    # 현재 달 -> 이후 달 -> 이전 달 순으로 정렬
    current_month_festivals.sort(key=lambda x: x["eventstartdate"])
    upcoming_festivals.sort(key=lambda x: x["eventstartdate"])
    past_festivals.sort(key=lambda x: x["eventstartdate"], reverse=True)

    sorted_festivals = current_month_festivals + upcoming_festivals + past_festivals
    data["response"]["body"]["items"]["item"] = sorted_festivals

    return jsonify(data)
# 2. 소개정보조회 API
@app.route('/api/intro', methods=['GET'])
def get_intro():
    content_id = request.args.get('contentId')

    if not content_id:
        return jsonify({"error": "Missing required parameters: contentId"}), 400

    params = {
        "contentId": content_id,
        "contentTypeId": 15
    }
    data = call_api("detailIntro1", params)
    return jsonify(data)
    
# 3. 공통정보조회 API
@app.route('/api/common', methods=['GET'])
def get_common():
    content_id = request.args.get('contentId')

    if not content_id:
        return jsonify({"error": "Missing required parameter: contentId"}), 400

    # 기본 정보 조회
    params = {
        "contentId": content_id,
        "defaultYN": "Y",
        "firstImageYN": "Y",
        "addrinfoYN": "Y",
        "overviewYN": "Y",
        "_type": "json"
    }
    data = call_api("detailCommon1", params)

    # 만약 기본 정보 조회에서 기간 정보가 없다면 추가로 detailIntro1 호출
    if data and 'response' in data and 'body' in data['response']:
        items = data['response']['body'].get('items', {}).get('item', [{}])
        if items and isinstance(items, list) and len(items) > 0:
            item = items[0]
            # 기간 정보가 없으면 추가 조회
            if not item.get('eventstartdate') or not item.get('eventenddate'):
                # 기간 정보를 가져오기 위해 detailIntro1 호출
                intro_params = {
                    "contentId": content_id,
                    "contentTypeId": 15,
                    "_type": "json"
                }
                intro_data = call_api("detailIntro1", intro_params)

                # 기간 정보가 있으면 추가
                if intro_data and 'response' in intro_data and 'body' in intro_data['response']:
                    intro_items = intro_data['response']['body'].get('items', {}).get('item', [{}])
                    if intro_items and isinstance(intro_items, list) and len(intro_items) > 0:
                        intro_item = intro_items[0]
                        item['eventstartdate'] = intro_item.get('eventstartdate')
                        item['eventenddate'] = intro_item.get('eventenddate')

    return jsonify(data)

# 4. 위치기반 관광정보 조회 API
@app.route('/api/nearbyFestivals', methods=['GET'])
def get_nearby_festivals():
    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')
    radius = request.args.get('radius', 5000)  # 기본 반경은 5km

    if not latitude or not longitude:
        return jsonify({"error": "Missing required parameters: latitude, longitude"}), 400

    params = {
        "mapX": longitude,
        "mapY": latitude,
        "radius": radius,
        "contentTypeId": 15  # 축제/행사
    }
    data = call_api("locationBasedList1", params)
    return jsonify(data)

# 5. 키워드 검색 조회 API
@app.route('/api/searchFestivals', methods=['GET'])
def search_festivals():
    keyword = request.args.get('keyword')

    if not keyword:
        return jsonify({"error": "Missing required parameter: keyword"}), 400

    params = {
        "keyword": keyword,
        "contentTypeId": 15  # 축제/행사
    }
    data = call_api("searchKeyword1", params)
    return jsonify(data)


if __name__ == '__main__':
    # Render에서 제공하는 포트 사용
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)