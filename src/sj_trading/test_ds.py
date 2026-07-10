"""測試 DeepSeek 連線"""
from openai import OpenAI

DS_KEY = "sk-d1a…5dd9"  # 請換成你的真實完整key

client = OpenAI(api_key=DS_KEY, base_url="https://api.deepseek.com/v1")

print("測試 DeepSeek 連線...")
try:
    r = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "用一句話10字內形容個股核心題材"},
            {"role": "user", "content": "3017 奇鋐"}
        ],
        temperature=0.2,
        timeout=10
    )
    print("✅ 成功:", r.choices[0].message.content)
except Exception as e:
    print("❌ 失敗:", e)
