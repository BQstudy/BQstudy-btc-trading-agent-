"""
LLM 客户端 - 支持多种LLM API
包括 Anthropic Claude、OpenAI兼容API（如腾讯云Kimi）
支持扩展思考（Extended Thinking）和思维链日志
"""

import os
import json
import yaml
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 尝试导入anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# 尝试导入openai
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class LLMResponse:
    """LLM响应"""
    id: str
    content: str
    thinking: str = ""  # 扩展思考内容
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: str = ""


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: str = "openai"  # openai/anthropic/custom
    api_key: str = ""
    base_url: str = ""  # 自定义API地址
    model: str = "kimi-k2.5"
    max_tokens: int = 8000
    thinking_budget: int = 5000
    temperature: float = 0.7
    top_p: float = 0.9

    def get_endpoint(self) -> str:
        """获取完整的API endpoint"""
        if self.provider == "custom" and self.base_url:
            # 自定义API，使用完整URL
            base = self.base_url.rstrip('/')
            if "/v1" not in base:
                base += "/v1"
            return f"{base}/chat/completions"
        return ""

    @classmethod
    def from_config(cls, config_path: str = "config/settings.yaml") -> "LLMConfig":
        """从配置文件加载"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                llm_config = config.get("llm", {})
                return cls(
                    provider=llm_config.get("provider", "openai"),
                    api_key=os.environ.get("ANTHROPIC_API_KEY", llm_config.get("api_key", "")),
                    base_url=llm_config.get("base_url", ""),
                    model=llm_config.get("model", "kimi-k2.5"),
                    max_tokens=llm_config.get("max_tokens", 8000),
                    thinking_budget=llm_config.get("thinking_budget", 5000),
                    temperature=llm_config.get("temperature", 0.7),
                    top_p=llm_config.get("top_p", 0.9)
                )
        except Exception:
            return cls()


class LLMClient:
    """
    LLM API 客户端
    支持Anthropic Claude和OpenAI兼容API（如腾讯云Kimi）
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_config()
        self.client = None

        # 根据provider初始化不同的客户端
        if self.config.provider == "anthropic":
            if ANTHROPIC_AVAILABLE and self.config.api_key:
                self.client = anthropic.Anthropic(api_key=self.config.api_key)
            else:
                print("Warning: Anthropic SDK not available or API key not set")
        elif self.config.provider == "openai" or self.config.provider == "custom":
            if OPENAI_AVAILABLE and self.config.api_key:
                client_kwargs = {"api_key": self.config.api_key}
                if self.config.base_url:
                    # 直接使用配置中的base_url（用户应配置完整URL）
                    base_url = self.config.base_url.rstrip('/')
                    client_kwargs["base_url"] = base_url
                self.client = OpenAI(**client_kwargs)
                print(f"OpenAI client initialized with base_url: {client_kwargs.get('base_url', 'default')}")
            else:
                print("Warning: OpenAI SDK not available or API key not set")
        else:
            print(f"Warning: Unknown provider {self.config.provider}")

        # 日志记录器
        from .cot_logger import CoTLogger
        self.logger = CoTLogger()

    def call(
        self,
        system_prompt: str,
        user_message: str,
        enable_thinking: bool = True,
        temperature: Optional[float] = None,
        phase: str = "general"
    ) -> LLMResponse:
        """
        调用LLM

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            enable_thinking: 是否启用扩展思考
            temperature: 温度参数
            phase: 阶段标识（用于日志）

        Returns:
            LLMResponse对象
        """
        if not self.client:
            raise RuntimeError("LLM client not initialized. Check API key.")

        # 根据provider调用不同的API
        if self.config.provider == "anthropic":
            return self._call_anthropic(system_prompt, user_message, enable_thinking, temperature, phase)
        elif self.config.provider == "openai" or self.config.provider == "custom":
            return self._call_openai(system_prompt, user_message, enable_thinking, temperature, phase)
        else:
            raise RuntimeError(f"Unknown provider: {self.config.provider}")

    def _call_anthropic(
        self,
        system_prompt: str,
        user_message: str,
        enable_thinking: bool,
        temperature: Optional[float],
        phase: str
    ) -> LLMResponse:
        """调用Anthropic API"""
        # 构建消息
        messages = [{"role": "user", "content": user_message}]

        # 构建请求参数
        params = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }

        # 扩展思考
        if enable_thinking:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget
            }

        # 温度
        params["temperature"] = temperature or self.config.temperature
        params["top_p"] = self.config.top_p

        # 调用API
        response = self.client.messages.create(**params)

        # 解析响应
        content = ""
        thinking = ""

        for block in response.content:
            if block.type == "thinking":
                thinking = block.thinking
            elif block.type == "text":
                content = block.text

        # 记录日志
        call_id = self.logger.log(
            phase=phase,
            chain_of_thought=thinking,
            decision={"response": content},
            market_context=None,
            prompt=system_prompt + "\n\n" + user_message
        )

        return LLMResponse(
            id=call_id,
            content=content,
            thinking=thinking,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self.config.model,
            stop_reason=response.stop_reason or ""
        )

    def _call_openai(
        self,
        system_prompt: str,
        user_message: str,
        enable_thinking: bool,
        temperature: Optional[float],
        phase: str
    ) -> LLMResponse:
        """调用OpenAI兼容API（如腾讯云Kimi）"""
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # 构建请求参数
        params = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": temperature or self.config.temperature,
            "top_p": self.config.top_p,
        }

        # 调用API
        response = self.client.chat.completions.create(**params)

        # 解析响应
        content = response.choices[0].message.content or ""
        thinking = ""  # OpenAI API通常没有单独的thinking字段

        # 尝试从reasoning_content获取（某些API支持）
        if hasattr(response.choices[0].message, 'reasoning_content'):
            thinking = response.choices[0].message.reasoning_content or ""

        # 记录日志
        call_id = self.logger.log(
            phase=phase,
            chain_of_thought=thinking,
            decision={"response": content},
            market_context=None,
            prompt=system_prompt + "\n\n" + user_message
        )

        return LLMResponse(
            id=call_id,
            content=content,
            thinking=thinking,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=self.config.model,
            stop_reason=response.choices[0].finish_reason or ""
        )

    def call_with_yaml_prompt(
        self,
        yaml_path: str,
        user_variables: Dict[str, Any],
        enable_thinking: bool = True,
        phase: str = "general"
    ) -> LLMResponse:
        """
        使用YAML提示词文件调用LLM

        Args:
            yaml_path: YAML提示词文件路径
            user_variables: 用户变量
            enable_thinking: 是否启用扩展思考
            phase: 阶段标识

        Returns:
            LLMResponse对象
        """
        # 加载YAML
        with open(yaml_path, 'r', encoding='utf-8') as f:
            prompt_config = yaml.safe_load(f)

        # 获取系统提示词
        system_prompt = prompt_config.get("system_prompt", "")

        # 获取用户消息模板
        user_template = prompt_config.get("user_message_template", "")

        # 填充变量
        user_message = user_template
        for key, value in user_variables.items():
            placeholder = "{" + key + "}"
            user_message = user_message.replace(placeholder, str(value))

        # 调用LLM
        return self.call(
            system_prompt=system_prompt,
            user_message=user_message,
            enable_thinking=enable_thinking,
            phase=phase
        )

    def parse_json_response(self, response: LLMResponse) -> Dict:
        """解析JSON响应"""
        try:
            # 尝试直接从content解析
            return json.loads(response.content)
        except json.JSONDecodeError:
            # 尝试提取JSON块
            content = response.content
            # 查找JSON块
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    return json.loads(content[start:end].strip())
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    return json.loads(content[start:end].strip())
            # 如果都失败，返回原始内容
            return {"raw_content": content, "error": "Failed to parse JSON"}


class MultiRoleClient:
    """
    多角色LLM客户端
    支持为不同角色设置不同参数
    """

    def __init__(self, base_client: LLMClient):
        self.base_client = base_client

        # 角色配置
        self.role_configs = {
            "bull": {"temperature": 0.8, "top_p": 0.9},
            "bear": {"temperature": 0.9, "top_p": 0.9},
            "neutral": {"temperature": 0.7, "top_p": 0.8},
            "risk": {"temperature": 0.6, "top_p": 0.7},
            "judge": {"temperature": 0.5, "top_p": 0.7},
        }

    def call_role(
        self,
        role: str,
        system_prompt: str,
        user_message: str,
        enable_thinking: bool = True,
        phase: str = "judgment"
    ) -> LLMResponse:
        """
        调用特定角色的LLM

        Args:
            role: 角色名称
            system_prompt: 系统提示词
            user_message: 用户消息
            enable_thinking: 是否启用扩展思考
            phase: 阶段标识

        Returns:
            LLMResponse对象
        """
        config = self.role_configs.get(role, {})

        return self.base_client.call(
            system_prompt=system_prompt,
            user_message=user_message,
            enable_thinking=enable_thinking,
            temperature=config.get("temperature"),
            phase=f"{phase}_{role}"
        )

    def call_debate(
        self,
        system_prompts: Dict[str, str],
        user_message: str,
        phase: str = "judgment"
    ) -> Dict[str, LLMResponse]:
        """
        并行调用多角色辩论

        Args:
            system_prompts: 角色名称 -> 系统提示词 的映射
            user_message: 用户消息
            phase: 阶段标识

        Returns:
            角色名称 -> LLM响应 的映射
        """
        responses = {}

        # 并行调用（简化实现，实际可用asyncio）
        for role, system_prompt in system_prompts.items():
            responses[role] = self.call_role(
                role=role,
                system_prompt=system_prompt,
                user_message=user_message,
                enable_thinking=False,  # 辩论时关闭扩展思考
                phase=phase
            )

        return responses


def create_llm_client(config_path: str = "config/settings.yaml") -> LLMClient:
    """
    创建LLM客户端的工厂函数

    Args:
        config_path: 配置文件路径

    Returns:
        LLMClient实例
    """
    config = LLMConfig.from_config(config_path)
    return LLMClient(config)


# 测试代码
if __name__ == "__main__":
    # 简单测试
    client = create_llm_client()

    if client.client:
        print("LLM Client initialized successfully")

        # 测试调用
        try:
            response = client.call(
                system_prompt="你是一个有帮助的助手。",
                user_message="你好，请介绍一下自己。",
                enable_thinking=False
            )
            print(f"Response: {response.content[:200]}...")
            print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")
        except Exception as e:
            print(f"API call failed: {e}")
    else:
        print("Warning: LLM client not initialized - check API key")
