"""
API Key诊断测试脚本
用于验证腾讯云LKEAP API Key是否有效
"""

import requests
import sys
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_api_key(api_key: str, base_url: str = "https://api.lkeap.cloud.tencent.com/coding/v3"):
    """测试API Key是否有效"""

    print("=" * 60)
    print("腾讯云LKEAP API Key诊断工具")
    print("=" * 60)

    # 检查API Key格式
    print(f"\n1. API Key格式检查:")
    print(f"   Key前缀: {api_key[:10]}...")
    print(f"   Key长度: {len(api_key)} 字符")

    if not api_key.startswith("sk-"):
        print("   [X] 错误: API Key应该以 'sk-' 开头")
        return False
    print("   [OK] Key格式正确 (以sk-开头)")

    # 测试模型列表接口
    print(f"\n2. 测试 /v1/models 接口:")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    models_url = f"{base_url}/models"
    print(f"   URL: {models_url}")

    try:
        response = requests.get(models_url, headers=headers, timeout=10)
        print(f"   状态码: {response.status_code}")

        if response.status_code == 200:
            print("   [OK] API Key有效!")
            data = response.json()
            if "data" in data:
                print(f"   可用模型数量: {len(data['data'])}")
                for model in data['data'][:5]:
                    print(f"     - {model.get('id', 'unknown')}")
            return True
        elif response.status_code == 401:
            print("   [X] 401 未授权 - API Key无效或已过期")
            print("\n   可能的原因:")
            print("   - API Key未在腾讯云LKEAP控制台创建")
            print("   - API Key已被删除或禁用")
            print("   - API Key所属账号欠费")
            print("\n   解决方法:")
            print("   1. 访问 https://console.cloud.tencent.com/lkeap")
            print("   2. 确认已开通LKEAP服务")
            print("   3. 创建新的API Key")
            return False
        else:
            print(f"   [X] 错误: {response.text}")
            return False

    except Exception as e:
        print(f"   [X] 请求异常: {e}")
        return False


def test_chat_completion(api_key: str, base_url: str = "https://api.lkeap.cloud.tencent.com/coding/v3"):
    """测试聊天补全接口"""

    print(f"\n3. 测试 /v1/chat/completions 接口:")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "kimi-k2.5",
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 100
    }

    chat_url = f"{base_url}/chat/completions"
    print(f"   URL: {chat_url}")
    print(f"   模型: {payload['model']}")

    try:
        response = requests.post(chat_url, headers=headers, json=payload, timeout=30)
        print(f"   状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            print(f"   [OK] 调用成功!")
            print(f"   响应: {content[:50]}...")
            return True
        else:
            print(f"   ❌ 错误: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        return False


if __name__ == "__main__":
    # 从配置文件读取
    import yaml
    import os

    config_path = "config/settings.yaml"

    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    llm_config = config.get("llm", {})
    api_key = llm_config.get("api_key", "")
    base_url = llm_config.get("base_url", "https://api.lkeap.cloud.tencent.com/v1")

    if not api_key:
        print("错误: 配置文件中未找到API Key")
        sys.exit(1)

    # 运行测试
    models_ok = test_api_key(api_key, base_url)

    if models_ok:
        chat_ok = test_chat_completion(api_key, base_url)

    print("\n" + "=" * 60)
    if models_ok:
        print("[OK] 诊断完成: API Key有效，可以正常使用")
    else:
        print("[X] 诊断完成: API Key无效，请检查配置")
    print("=" * 60)
