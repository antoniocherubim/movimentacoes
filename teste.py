import requests

API_KEY = "43b2a59fd77f5332f44343476490221d"
response = requests.post(
    "http://2captcha.com/in.php",
    data={
        "key": API_KEY,
        "method": "test",
        "json": 1
    }
)

print(response.json())  