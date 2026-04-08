"""
自定义LLM客户端 - 支持腾讯云Kimi API
使用原生HTTP请求调用API
"""

import requests
import json
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class CustomLLMResponse:
    """自定义LLM响应"""
    id: str
    content: str
    thinking: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: str = ""


class CustomLLMClient:
    """
    自定义LLM客户端
    支持腾讯云Kimi等OpenAI兼容API
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.lkeap.cloud.tencent.com",
        model: str = "kimi-k2.5"
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.session = requests.Session()

    def call(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 8000
    ) -> CustomLLMResponse:
        """
        调用LLM API

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            CustomLLMResponse对象
        """
        # 构建请求
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # 发送请求
        response = self.session.post(url, headers=headers, json=payload, timeout=60)

        # 检查响应
        if response.status_code != 200:
            raise RuntimeError(f"API Error {response.status_code}: {response.text}")

        # 解析响应
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return CustomLLMResponse(
            id=data.get("id", ""),
            content=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=self.model,
            stop_reason=data["choices"][0].get("finish_reason", "")
        )


# 测试代码
if __name__ == "__main__":
    # 腾讯云Kimi API测试
    client = CustomLLMClient(
        api_key="sk-sp-qQKgztUaHwjapY5lblRg5KJ3tFgK4WYTgxIT20rw7u4hocom",
        base_url="https://api.lkeap.cloud.tencent.com",
        model="kimi-k2.5"
    )

    try:
        response = client.call(
            system_prompt="你是一个专业的BTC交易助手。",
            user_message="你好，请用一句话介绍自己。",
            temperature=0.7,
            max_tokens=200
        )
        print(f"Response: {response.content}")
        print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")
    except Exception as e:
        print(f"Error: {e}")
