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
BASE_URL = "https://apis.data.go.kr/B551011/KorService1/searchFestival1"

class SSLAdapter(HTTPAdapter):
    """ SSL/TLS 버전을 낮춰 호환성을 확보하는 어댑터 """
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

# API 호출 함수 정의
def get_api_data(event_start_date):
    url = f"{BASE_URL}?serviceKey={API_KEY}&MobileOS=AND&MobileApp=MyApp&_type=json&eventStartDate={event_start_date}"
    print("Request URL:", url)

    session = requests.Session()
    session.mount("https://", SSLAdapter())
    
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
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

# Flask 엔드포인트 설정
@app.route('/api/festivals', methods=['GET'])
def get_festivals():
    event_start_date = request.args.get('eventStartDate')
    if not event_start_date:
        return jsonify({"error": "Missing required parameter: eventStartDate"}), 400

    data = get_api_data(event_start_date)
    return jsonify(data)
    
if __name__ == '__main__':
    # Render에서 제공하는 포트 사용
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)