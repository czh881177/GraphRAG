import os
from dotenv import load_dotenv
from neo4j_graphrag.llm import OpenAILLM

# 加载 .env 文件中的环境变量
load_dotenv()

print("=" * 50)
print("🔍 正在测试 LLM (DeepSeek) 连接...")
print("=" * 50)

# 1. 检查环境变量是否读取成功
token = os.getenv("LLM_TOKEN")
endpoint = os.getenv("LLM_ENDPOINT")
model = os.getenv("LLM_MODEL", "deepseek-chat")

print(f"📌 读取到的配置：")
print(f"   - ENDPOINT: {endpoint}")
print(f"   - MODEL: {model}")
print(f"   - TOKEN: {token[:10]}...{token[-4:] if token and len(token) > 14 else '(未设置)'}")  # 只显示前后几位，防止泄露

if not token or token == "sk-xxxxxxxxxxxxxxxxxxxxxxxx":
    print("\n❌ 错误：LLM_TOKEN 未设置或仍是默认值！")
    print("   请用 notepad .env 编辑文件，填入你的真实 DeepSeek API Key。")
    exit(1)

print("\n✅ 环境变量读取正常，正在尝试调用 API...")

# 2. 初始化 LLM
try:
    llm = OpenAILLM(
        model_name=model,
        base_url=endpoint,
        api_key=token,
        model_params={"temperature": 0}
    )
    print("✅ LLM 客户端初始化成功")
except Exception as e:
    print(f"❌ LLM 客户端初始化失败：{e}")
    exit(1)

# 3. 发送测试请求（完全不需要数据库，纯 API 调用）
try:
    print("\n📤 发送测试问题：'请用一句话介绍阿司匹林。'")
    response = llm.invoke("请用一句话介绍阿司匹林。")
    print("\n" + "=" * 50)
    print("✅ LLM 响应成功！内容如下：")
    print("=" * 50)
    print(response)
    print("=" * 50)
    print("\n🎉 恭喜！你的 LLM 连接完全正常，可以继续后续开发。")
    
except Exception as e:
    print("\n" + "=" * 50)
    print("❌ LLM 调用失败！请检查以下可能原因：")
    print("=" * 50)
    print(f"报错信息：{e}")
    print("\n排查建议：")
    print("1. 检查 .env 中的 LLM_TOKEN 是否复制完整（没有多余空格）")
    print("2. 检查 LLM_ENDPOINT 是否为 https://api.deepseek.com/v1")
    print("3. 确认你的 DeepSeek 账户有余额或免费额度")
    print("4. 如果开了代理，检查代理是否干扰了网络请求")