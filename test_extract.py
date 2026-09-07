import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("LLM_TOKEN"),
    base_url=os.getenv("LLM_ENDPOINT", "https://api.deepseek.com/v1")
)

prompt = """
请从以下文本中提取医药相关的实体和关系。

文本：阿司匹林是一种非甾体抗炎药，通过抑制环氧合酶（COX）发挥解热镇痛作用。

请以JSON格式输出：
{
    "entities": [{"name": "实体名", "type": "实体类型"}],
    "relationships": [{"source": "源实体", "target": "目标实体", "type": "关系类型"}]
}
"""

response = client.chat.completions.create(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    messages=[{"role": "user", "content": prompt}],
    temperature=0
)

print("LLM 响应：")
print(response.choices[0].message.content)