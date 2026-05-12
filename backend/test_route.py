from flask import Flask
from routes import kaipai_bp

app = Flask(__name__)
app.register_blueprint(kaipai_bp)

print("Routes:")
for rule in app.url_map.iter_rules():
    if 'kaipai' in rule.endpoint or 'drafts' in rule.endpoint:
        print(f"  {rule.rule} -> {rule.endpoint}")

# 测试请求
with app.test_client() as client:
    response = client.get('/api/users/436bc399-e980-4305-bca6-55a0273749b8/kaipai/drafts')
    print(f"\nTest request status: {response.status_code}")
    if response.status_code != 404:
        print(f"Response: {response.get_json()}")
