from flask import Flask, jsonify, request
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import ssl
import os
from dotenv import load_dotenv

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

    if not event_start_date:
        return jsonify({"error": "Missing required parameter: eventStartDate"}), 400

    params = {
        "eventStartDate": event_start_date,
        "areaCode": area_code
    }

    data = call_api("searchFestival1", params)
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

    params = {
        "contentId": content_id,
        "defaultYN": "Y",
        "firstImageYN": "Y",
        "addrinfoYN": "Y",
        "overviewYN": "Y"
    }
    data = call_api("detailCommon1", params)
    return jsonify(data)

if __name__ == '__main__':
    # Render에서 제공하는 포트 사용
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)