"""
AI 语义重排模块
使用大语言模型优化 OCR 输出的排版和结构
"""

import asyncio
import httpx
import re
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from google import genai
from pydantic import BaseModel, Field

from app.config import settings

@dataclass
class ReformatResult:
    """重排结果"""
    original: str
    formatted: str
    success: bool
    error: Optional[str] = None
    ai_errors: Optional[List[str]] = None

class FormattedContent(BaseModel):
    formatted_text: str = Field(description="The corrected, reformatted, and improved text in Markdown format. Keep the original meaning but fix typos, layout, and punctuation.")

class AIReformatter:
    """AI 语义重排器"""
    
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        model: str = None,
        max_chunk_chars: int = 4000  # Gemini Flash 支持长上下文，增加分块大小
    ):
        self.api_key = api_key or getattr(settings, 'AI_API_KEY', '')
        self.api_url = api_url 
        # 如果未指定模型，且是 Gemini，使用较新的 Flash 模型
        self.model = model or getattr(settings, 'AI_MODEL', 'gemini-2.0-flash')
        self.max_chunk_chars = max_chunk_chars
        
        self.system_prompt = """你是一个专业的文档排版专家。你的任务是优化从 OCR（光学字符识别）提取的文本。
请遵循以下规则：
1. 修复明显的 OCR 错别字和识别错误
2. 还原正确的段落结构（合并被错误断开的句子）
3. 识别并格式化列表（有序/无序）
4. 保留原文的核心内容和语义，不要添加或删除信息
5. 使用 Markdown 格式输出
6. 如果是笔记内容，保持简洁的笔记风格"""

    def _split_into_chunks(self, text: str) -> List[str]:
        """将文本分割成适合 AI 处理的小块"""
        if len(text) <= self.max_chunk_chars:
            return [text]
        
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= self.max_chunk_chars:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # 如果单个段落太长，切分处理
                if len(para) > self.max_chunk_chars:
                    for i in range(0, len(para), self.max_chunk_chars):
                        chunks.append(para[i:i + self.max_chunk_chars])
                    current_chunk = ""
                else:
                    current_chunk = para + "\n\n"
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]

    async def _call_gemini_sdk(self, text: str) -> ReformatResult:
        """使用 Google GenAI SDK 调用"""
        try:
            client = genai.Client(api_key=self.api_key)
            
            # 在线程中运行同步 SDK 调用
            def call():
                return client.models.generate_content(
                    model=self.model,
                    contents=f"{self.system_prompt}\n\n待处理文本：\n{text}",
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": FormattedContent.model_json_schema(),
                    },
                )

            response = await asyncio.to_thread(call)
            
            # 解析结构化输出
            try:
                result_obj = FormattedContent.model_validate_json(response.text)
                formatted_text = result_obj.formatted_text
            except Exception as parse_err:
                # 降级：直接尝试获取文本
                print(f"解析 JSON 失败，尝试直接获取文本: {parse_err}")
                formatted_text = response.text

            return ReformatResult(
                original=text,
                formatted=formatted_text,
                success=True
            )
        except Exception as e:
            return ReformatResult(
                original=text,
                formatted=text,
                success=False,
                error=f"Gemini SDK Error: {str(e)}"
            )

    async def _call_openai_compatible(self, text: str, client: httpx.AsyncClient) -> ReformatResult:
        """使用 HTTP 调用 OpenAI 兼容接口 (DeepSeek/其他)"""
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.3
            }
            
            # 处理自定义 URL 路径
            base_url = self.api_url.rstrip('/')
            if not base_url.endswith('/v1/chat/completions'):
                if '/v1' not in base_url:
                    url = f"{base_url}/v1/chat/completions"
                else:
                    url = f"{base_url}/chat/completions" 
            else:
                url = base_url

            response = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                timeout=60.0
            )

            if response.status_code != 200:
                return ReformatResult(original=text, formatted=text, success=False, error=f"HTTP {response.status_code}: {response.text}")

            data = response.json()
            formatted = data['choices'][0]['message']['content']
            return ReformatResult(original=text, formatted=formatted, success=True)
            
        except Exception as e:
            return ReformatResult(original=text, formatted=text, success=False, error=str(e))

    async def _call_ai_api(self, text: str, client: httpx.AsyncClient) -> ReformatResult:
        """根据配置选择调用方式"""
        # 如果没有自定义 URL 或者 URL 为空，默认使用 Gemini SDK
        if not self.api_url or "googleapis.com" in self.api_url:
            return await self._call_gemini_sdk(text)
        else:
            # 有自定义 URL，假设是 OpenAI 兼容格式
            return await self._call_openai_compatible(text, client)

    async def reformat(self, text: str) -> Dict[str, Any]:
        """
        异步并行重排文本
        
        Args:
            text: OCR 提取的原始文本
            
        Returns:
            包含重排结果的字典
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "未配置 AI API Key",
                "original": text,
                "formatted": text,
                "chunks_processed": 0
            }
        
        chunks = self._split_into_chunks(text)
        
        async with httpx.AsyncClient() as client:
            # 并行发送所有请求
            tasks = [self._call_ai_api(chunk, client) for chunk in chunks]
            results = await asyncio.gather(*tasks)
        
        # 合并结果
        formatted_chunks = []
        errors = []
        success_count = 0
        
        for result in results:
            if result.success:
                formatted_chunks.append(result.formatted)
                success_count += 1
            else:
                formatted_chunks.append(result.original)
                if result.error:
                    errors.append(result.error)
        
        return {
            "success": len(errors) == 0,
            "original": text,
            "formatted": "\n\n".join(formatted_chunks),
            "chunks_total": len(chunks),
            "chunks_processed": success_count,
            "errors": errors if errors else None
        }

    async def reformat_pages(self, pages: List[Dict]) -> List[Dict]:
        """
        并行处理多个页面
        
        Args:
            pages: OCR 结果页面列表
            
        Returns:
            增强后的页面列表
        """
        if not self.api_key:
            return pages
        
        async def process_page(page: Dict) -> Dict:
            text = page.get("text", "")
            if not text.strip():
                return page
            
            result = await self.reformat(text)
            page["ai_formatted"] = result["formatted"]
            page["ai_success"] = result["success"]
            # 收集错误信息
            if result.get("errors"):
                page["ai_errors"] = result["errors"]
            return page
        
        tasks = [process_page(page) for page in pages]
        return await asyncio.gather(*tasks)


# 便捷函数
async def reformat_text(text: str, api_key: str = None) -> Dict[str, Any]:
    """快捷函数：重排文本"""
    reformatter = AIReformatter(api_key=api_key)
    return await reformatter.reformat(text)
