from g4f.client import Client

client = Client(api_key="sk-V2xkqFG7fmbLiDVULDhu3w")

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Write a 10-word test sentence."}]
    )
    print(response.choices[0].message.content)
except Exception as e:
    print("Error:", e)
