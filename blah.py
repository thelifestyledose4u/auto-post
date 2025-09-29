import requests

client_id = "263308558753-lsscpp7oi9r28k4jajuul0egovod4dvf.apps.googleusercontent.com"
client_secret = "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"
code = "4/0AVGzR1Bfg8yKl0VCO48loA1BGzvchcWlQSBTTyrGF1Ea79-irWkK6LlnzdxZszE43o4B2Q"
redirect_uri = "http://localhost:8080/"

token_url = "https://oauth2.googleapis.com/token"
data = {
    "client_id": client_id,
    "client_secret": client_secret,
    "code": code,
    "grant_type": "authorization_code",
    "redirect_uri": redirect_uri,
}

response = requests.post(token_url, data=data)
print(response.json())