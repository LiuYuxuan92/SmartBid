"""LLM调用与技术标生成模块

负责组装 prompt（项目简介 + 检索上下文），调用 LLM API（60秒超时），
支持指数退避重试（最多3次），无相关文档时使用通用模板。
"""

import time
import logging
from typing import Optional

import httpx

from src.exceptions import LLMAPIError
from src.rag_generator.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

GENERIC_TEMPLATE = """
# 技术标文档

## 公司简介
[请填写公司简介]

## 技术方案
{project_brief}

## 项目进度计划
[请填写进度计划]

## 质量保证措施
[请填写质量保证措施]
"""


class BidGenerator:
    """技术标生成器 - 调用LLM API生成投标文档"""

    def __init__(self, api_key: str, api_url: str, model: str = "gpt-4",
                 timeout: int = 60, max_retries: int = 3):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def generate(self, project_brief: str, context_chunks: list[RetrievalResult]) -> str:
        """生成技术标文本

        Args:
            project_brief: 项目简介
            context_chunks: 检索到的相关历史文档分块

        Returns:
            生成的技术标文本

        Raises:
            LLMAPIError: 所有重试用尽后
        """
        if not context_chunks:
            # No relevant docs found, use generic template
            logger.info("No relevant historical documents, using generic template")
            return GENERIC_TEMPLATE.format(project_brief=project_brief)

        prompt = self._compose_prompt(project_brief, context_chunks)
        return self._call_llm_with_retry(prompt)

    def _compose_prompt(self, brief: str, chunks: list[RetrievalResult]) -> str:
        """组装prompt"""
        context_text = "\n\n---\n\n".join(
            f"[来源: {r.chunk.metadata.get('source_doc', '未知')}]\n{r.chunk.text}"
            for r in chunks
        )

        prompt = f"""基于以下历史标书参考资料和项目简介，生成一份完整的技术标文档。

## 项目简介
{brief}

## 参考资料
{context_text}

## 要求
请生成包含以下章节的技术标：
1. 公司简介
2. 技术方案
3. 项目进度计划
4. 质量保证措施

请确保内容专业、完整、符合投标要求。"""

        return prompt

    def _call_llm_with_retry(self, prompt: str) -> str:
        """调用LLM API，带指数退避重试

        Raises:
            LLMAPIError: 所有重试失败
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return self._call_llm(prompt)
            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt  # exponential backoff: 1, 2, 4 seconds
                logger.warning(
                    "LLM API attempt %d/%d failed: %s. Retrying in %ds",
                    attempt + 1, self.max_retries, str(e), wait_time
                )
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)

        raise LLMAPIError(f"All {self.max_retries} retry attempts failed. Last error: {last_error}")

    def _call_llm(self, prompt: str) -> str:
        """单次LLM API调用"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个专业的投标文件编写助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
