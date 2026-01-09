"""
AI 语义重排模块
使用大语言模型优化 OCR 输出的排版和结构
"""

import asyncio
import httpx
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import re

from app.config import settings


@dataclass
class ReformatResult:
    """重排结果"""
    original: str
    formatted: str
    success: bool
    error: Optional[str] = None


class AIReformatter:
    """AI 语义重排器"""
    
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        model: str = None,
        max_chunk_chars: int = 2000  # 每段最大字符数
    ):
        self.api_url = api_url or getattr(settings, 'AI_API_URL', 'https://api.openai.com/v1/chat/completions')
        self.api_key = api_key or getattr(settings, 'AI_API_KEY', '')
        self.model = model or getattr(settings, 'AI_MODEL', 'gpt-4o-mini')
        self.max_chunk_chars = max_chunk_chars
        
        self.system_prompt = """你是一个专业的文档排版专家。你的任务是优化从 OCR（光学字符识别）提取的文本。

请遵循以下规则：
1. 修复明显的 OCR 错别字和识别错误
2. 还原正确的段落结构（合并被错误断开的句子）
3. 识别并格式化列表（有序/无序）
4. 保留原文的核心内容和语义，不要添加或删除信息
5. 使用 Markdown 格式输出
6. 如果是笔记内容，保持简洁的笔记风格

直接输出优化后的文本，不要添加任何解释或前言。"""

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
                # 如果单个段落太长，按句子分割
                if len(para) > self.max_chunk_chars:
                    sentences = re.split(r'(?<=[。！？.!?])\s*', para)
                    temp = ""
                    for sent in sentences:
                        if len(temp) + len(sent) <= self.max_chunk_chars:
                            temp += sent
                        else:
                            if temp:
                                chunks.append(temp.strip())
                            temp = sent
                    if temp:
                        current_chunk = temp + "\n\n"
                    else:
                        current_chunk = ""
                else:
                    current_chunk = para + "\n\n"
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]

    async def _call_ai_api(self, text: str, client: httpx.AsyncClient) -> ReformatResult:
        """调用 AI API 处理单个文本块"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"请优化以下 OCR 文本的排版：\n\n{text}"}
                ],
                "temperature": 0.3,
                "max_tokens": 4000
            }
            
            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=60.0
            )
            
            if response.status_code != 200:
                return ReformatResult(
                    original=text,
                    formatted=text,
                    success=False,
                    error=f"API 错误: {response.status_code}"
                )
            
            data = response.json()
            formatted = data['choices'][0]['message']['content']
            
            return ReformatResult(
                original=text,
                formatted=formatted,
                success=True
            )
            
        except Exception as e:
            return ReformatResult(
                original=text,
                formatted=text,
                success=False,
                error=str(e)
            )

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
            return page
        
        tasks = [process_page(page) for page in pages]
        return await asyncio.gather(*tasks)


# 便捷函数
async def reformat_text(text: str, api_key: str = None) -> Dict[str, Any]:
    """快捷函数：重排文本"""
    reformatter = AIReformatter(api_key=api_key)
    return await reformatter.reformat(text)
