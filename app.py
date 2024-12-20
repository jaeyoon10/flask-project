from flask import Flask, jsonify, request
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import ssl
import os
from dotenv import load_dotenv
from datetime import datetime
import re  # 추가

# .env 파일에서 환경 변수 로드
load_dotenv()

# Flask 앱 초기화
app = Flask(__name__)

def clean_html_tags(text):
    """HTML 태그를 제거하는 함수"""
    if text:
        return re.sub(r'<br\s*/?>', ' ', text)  # <br>을 줄바꿈 문자로 변환
    return text

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
    area_code = request.args.get('areaCode')  # 추가된 부분: areaCode 가져오기
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('pageSize', 500))
    
    current_date = datetime.now()
    current_year = current_date.year
    current_year_month = current_date.strftime("%Y%m")
    
    params = {
        "eventStartDate": current_date.strftime("%Y0101"),
        "eventEndDate": current_date.strftime("%Y1231"),
        "pageNo": page,
        "numOfRows": page_size,
        "_type": "json"
    }

    # 만약 areaCode가 주어지면 필터에 추가합니다.
    if area_code:
        params["areaCode"] = area_code

    # 한국관광공사 API 호출
    data = call_api("searchFestival1", params)
    festivals = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

    # 날짜를 "yyyyMMdd" 형식으로 파싱하는 함수
    def parse_date(date_str):
        return datetime.strptime(date_str, "%Y%m%d") if date_str else None

    # 축제 데이터를 현재 달, 이후 달, 과거 달로 분류합니다.
    current_month = []
    upcoming = []
    past = []

    for festival in festivals:
        start_date = festival.get("eventstartdate")
        parsed_date = parse_date(start_date) if start_date else None

        if parsed_date:
            # 현재 연도 및 현재 달의 축제
            if parsed_date.year == current_year and parsed_date.strftime("%Y%m") == current_year_month:
                current_month.append(festival)
            # 미래 연도 및 월의 축제
            elif parsed_date.year > current_year or (parsed_date.year == current_year and parsed_date.month > current_date.month):
                upcoming.append(festival)
            # 과거 연도 및 월의 축제
            else:
                past.append(festival)
                
    # 각 리스트를 정렬합니다.
    current_month.sort(key=lambda x: x["eventstartdate"])
    upcoming.sort(key=lambda x: x["eventstartdate"])
    past.sort(key=lambda x: x["eventstartdate"], reverse=True)

    # 현재 달 -> 이후 달 -> 과거 달 순으로 병합합니다.
    sorted_festivals = current_month + upcoming + past
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

    # 가격 및 이용 시간 정보 포함
    if data and 'response' in data and 'body' in data['response']:
        items = data['response']['body'].get('items', {}).get('item', [{}])
        if items and isinstance(items, list) and len(items) > 0:
            for item in items:
                if 'usetimefestival' in item:
                    item['usetimefestival'] = clean_html_tags(item['usetimefestival'])
                if 'playtime' in item:
                    item['playtime'] = clean_html_tags(item['playtime'])

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

            # 연락처에 <br> 태그 제거
            if 'tel' in item:
                item['tel'] = clean_html_tags(item['tel'])
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



# 지역 코드 캐싱
cached_area_codes = None  # 전역 변수로 캐싱

@app.route('/api/areaCodes', methods=['GET'])
def get_area_codes():
    global cached_area_codes
    if cached_area_codes is None:  # 캐싱된 데이터가 없을 경우 API 호출
        params = {"_type": "json"}
        data = call_api("areaCode1", params)
        if "response" in data:  # 성공적으로 데이터를 가져왔을 경우
            cached_area_codes = data
    return jsonify(cached_area_codes)

    # 지역 코드 매핑
area_code_mapping = {
    "서울": 1,
    "인천": 2,
    "대전": 3,
    "대구": 4,
    "광주": 5,
    "부산": 6,
    "울산": 7,
    "세종": 8,
    "경기": 31,
    "강원": 32,
    "충북": 33,
    "충남": 34,
    "경북": 35,
    "경남": 36,
    "전북": 37,
    "전남": 38,
    "제주": 39,
}

# 6. 지역 코드 조회 API
@app.route('/api/regionFestivals', methods=['GET'])
def get_region_festivals():
    region_name = request.args.get('regionName')  # 지역 이름 (예: "세종")
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('pageSize', 10))

    # 지역 코드 찾기
    area_code = area_code_mapping.get(region_name)

    if not area_code:
        return jsonify({"error": f"Invalid region name: {region_name}"}), 400

    # API 호출 파라미터
    params = {
        "areaCode": area_code,
        "pageNo": page,
        "numOfRows": page_size,
        "_type": "json"
    }

    # API 호출
    data = call_api("searchFestival1", params)
    return jsonify(data)

if __name__ == '__main__':
    # Render에서 제공하는 포트 사용
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)