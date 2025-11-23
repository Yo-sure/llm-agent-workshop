import requests
import uuid

url = "http://127.0.0.1:7860/api/v1/run/c7d30eff-01e0-4743-aed3-975e9265073f"

# Headers with API key
headers = {
    "Content-Type": "application/json",
    "x-api-key": "sk-Ug1vBynGxoIThqJbWyc8_fYk-6MjULX_1_dDdqVbSq4"
}

# Request payload configuration
payload = {
    "output_type": "chat",
    "input_type": "chat",
    "input_value": "AAPL news summary"
}
payload["session_id"] = str(uuid.uuid4())

print(f"📤 요청 전송 중...")
print(f"   URL: {url}")
print(f"   Payload: {payload}")

try:
    # Send API request with timeout
    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    # Print response
    print(f"\n✅ 응답 성공!")
    print(f"   Status: {response.status_code}")
    print(f"   Response length: {len(response.text)}")
    print(f"\n📄 Response:\n{response.text[:500]}")
except requests.exceptions.Timeout:
    print(f"❌ 타임아웃 (60초)")
except requests.exceptions.RequestException as e:
    print(f"❌ API 요청 실패: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"   Response: {e.response.text}")
except ValueError as e:
    print(f"❌ 응답 파싱 실패: {e}")

