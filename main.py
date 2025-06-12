from __future__ import annotations

import re
import base64
from urllib.parse import quote
from pkg.platform.sources.lark import LarkAdapter
from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from pkg.platform.types import message as platform_message
from lark_oapi.api.im.v1 import *
import json

@register(name='LarkEnhance', description='飞书消息增强插件', version='0.1.0', author='axdlee')
class LarkEnhance(BasePlugin):
    """飞书消息增强插件，用于增强飞书消息的处理能力"""

    def __init__(self, host: APIHost):
        self.host = host
        super().__init__(host)
        self.host.ap.logger.info("[LarkEnhance] 插件已加载")

    async def initialize(self):
        """异步初始化"""
        pass

    async def get_message_content(self, adapter: LarkAdapter, message_id: str) -> str | None:
        """
        获取消息的内容，包括原始消息和引用消息
        
        Args:
            adapter: 飞书适配器
            message_id: 消息ID
            
        Returns:
            str | None: 合并后的消息内容，如果获取失败则返回 None
        """
        try:
            msg_resp = await adapter.api_client.im.v1.message.aget(
                GetMessageRequest.builder().message_id(message_id).build()
            )
            self.host.ap.logger.debug(f"[LarkEnhance] 获取到的消息: {msg_resp}")
            if msg_resp and msg_resp.data and msg_resp.data.items:
                msg = msg_resp.data.items[0]  # 获取第一条消息
                self.host.ap.logger.debug(f"[LarkEnhance] 获取到的消息: {msg}")
                # 如果有父消息ID，获取引用消息内容
                if msg.parent_id:
                    parent_resp = await adapter.api_client.im.v1.message.aget(
                        GetMessageRequest.builder().message_id(msg.parent_id).build()
                    )
                    
                    if parent_resp and parent_resp.data and parent_resp.data.items:
                        # 收集所有引用消息的内容
                        parent_contents = []
                        for parent_msg in parent_resp.data.items:
                            if parent_msg.msg_type == 'text' and parent_msg.body and parent_msg.body.content:
                                try:
                                    content_json = json.loads(parent_msg.body.content)
                                    self.host.ap.logger.debug(f"[LarkEnhance] 获取到的消息内容: {content_json}")
                                    if isinstance(content_json, dict) and 'text' in content_json:
                                        parent_contents.append(content_json['text'])
                                except json.JSONDecodeError:
                                    self.host.ap.logger.warning(f"[LarkEnhance] 解析消息内容JSON失败: {parent_msg.body.content}")
                                    parent_contents.append(parent_msg.body.content)
                        self.host.ap.logger.debug(f"[LarkEnhance] 获取到的消息内容: {parent_contents}")
                        if parent_contents:
                            # 使用换行符连接所有内容
                            return '\n'.join(parent_contents)
                
        except Exception as e:
            self.host.ap.logger.warning(f"[LarkEnhance] 获取消息内容失败: {str(e)}")
        
        return None

    def convert_markdown_images_to_links(self, text: str) -> str:
        """
        将Markdown格式的图片语法转换为文本链接格式
        例如: ![image](http://example.com/image.jpg) -> [图片链接](http://example.com/image.jpg)
        注意：在飞书卡片中，必须使用普通链接语法，不能使用图片语法，否则会被当作image_key处理
        """
        # Markdown图片语法的正则表达式，支持多行匹配
        image_pattern = r'!\[(.*?)\]\((.*?)\)'
        
        # 替换为纯文本链接格式（不使用图片语法）
        def replace_to_link(match):
            alt_text = match.group(1)
            url = match.group(2)
            # 如果alt_text为空，使用默认文本
            display_text = alt_text if alt_text else "参考图"
            # 使用普通链接语法，不使用图片语法，并移除多余的换行符
            return f'[{display_text}](https://applink.feishu.cn/client/web_url/open?mode=sidebar-semi&max_width=800&reload=false&url={url})'
        
        return re.sub(image_pattern, replace_to_link, text, flags=re.DOTALL)

    def clean_markdown_code_blocks(self, text: str) -> str:
        """
        移除Markdown代码块的标记
        例如: ```markdown\nxxx\n``` -> \nxxx\n
        其他语言的代码块（如```python）保持不变
        """
        # 匹配整个markdown代码块，支持任意空白字符
        pattern = r'```markdown\s*(.*?)\s*```'
        
        def extract_content(match):
            return '\n' + match.group(1).strip() + '\n'
        
        return re.sub(pattern, extract_content, text, flags=re.DOTALL)
    

    def remove_tags_content(self, msg: str) -> str:
        """
        移除消息中的所有闭合的<think>、<details>、<summary>和<thinking>标签及其内容
        未闭合的标签将保持原样
        """
        # 用于存储处理后的消息
        processed_msg = msg
        
        # 定义需要处理的标签
        tags = ['think', 'details', 'summary', 'thinking']
        
        for tag in tags:
            # 匹配完整的闭合标签对（包含内容）
            pattern = rf'<{tag}\b[^>]*>[\s\S]*?</{tag}>'
            # 只处理闭合的标签
            processed_msg = re.sub(pattern, '', processed_msg, flags=re.IGNORECASE)
        
        # 优化换行处理：合并相邻空行但保留段落结构
        processed_msg = re.sub(r'\n{3,}', '\n\n', processed_msg)  # 三个以上换行转为两个
        processed_msg = re.sub(r'(\S)\n{2,}(\S)', r'\1\n\2', processed_msg)  # 正文间的多个空行转为单个
        
        return processed_msg.strip()

    async def process_empty_message(self, ctx: EventContext) -> None:
        """
        处理空消息的公共方法
        
        Args:
            ctx: 事件上下文
        """
        # 取得适配器对象
        adapter = ctx.event.query.adapter
        self.host.ap.logger.debug(f"[LarkEnhance] 适配器: {adapter}")
        # 如果适配器不是飞书，则不进行处理
        if not isinstance(adapter, LarkAdapter):
            return

        self.host.ap.logger.debug(f"[LarkEnhance] 消息: {ctx.event.text_message}")
        
        # 检查消息链中是否只包含 Source 和 At 消息
        has_other_content = False
        source_msg = None
        con_not_handle = False
        
        if hasattr(ctx.event, 'query') and ctx.event.query and ctx.event.query.message_chain:
            self.host.ap.logger.debug(f"[LarkEnhance] 消息链: {ctx.event.query.message_chain}")
            for msg in ctx.event.query.message_chain:
                if isinstance(msg, platform_message.Source):
                    source_msg = msg
                elif isinstance(msg, (platform_message.Image, platform_message.Voice, platform_message.File)):
                    con_not_handle = True
                    break
                elif isinstance(msg, platform_message.At):
                    continue
                elif not isinstance(msg, (platform_message.Source, platform_message.At)):
                    has_other_content = True
                    break

        # 如果消息链中包含图片、语音、文件等非文本消息，则不进行处理
        if con_not_handle:
            ctx.event.alter = "我暂时还无法处理图片、语音、文件等非文本消息， 请使用文本消息与我交流"
            ctx.add_return("reply", ["我暂时还无法处理图片、语音、文件等非文本消息， 请使用文本消息与我交流"])
            # 阻止默认行为
            ctx.prevent_default()

        # 如果消息链中包含其他内容，则不进行处理
        if has_other_content:
            self.host.ap.logger.debug(f"[LarkEnhance] 消息链中包含其他内容，不进行处理")
            return
        
        # 如果消息链中只有 Source 和 At，则尝试获取引用消息内容
        if not has_other_content and source_msg:
            self.host.ap.logger.debug(f"[LarkEnhance] 检测到空消息，尝试处理消息链")
            self.host.ap.logger.debug(f"[LarkEnhance] 获取到消息链中的 Source 消息: {source_msg.id}")
            
            try:
                # 获取消息内容
                content = await self.get_message_content(adapter, source_msg.id)
                self.host.ap.logger.debug(f"[LarkEnhance] 获取到的消息内容: {content}")
                if content:
                    ctx.event.alter = content
                    self.host.ap.logger.debug(f"[LarkEnhance] 使用消息内容: {content}")
                    return
            except Exception as e:
                self.host.ap.logger.warning(f"[LarkEnhance] 获取消息内容失败: {str(e)}")
        
        self.host.ap.logger.info(f"[LarkEnhance] 消息内容: {ctx.event.text_message}")
        # 默认返回
        self.host.ap.logger.debug("[LarkEnhance] 获取不到引用内容，返回默认回复")
        ctx.event.alter = "请问有什么可以帮助你？"
        ctx.add_return("reply", ["请问有什么可以帮助你？"])
        # 阻止默认行为
        ctx.prevent_default()
            

    @handler(PersonNormalMessageReceived)
    async def on_person_message(self, ctx: EventContext):
        """处理个人消息"""
        await self.process_empty_message(ctx)

    @handler(GroupNormalMessageReceived)
    async def on_group_message(self, ctx: EventContext):
        """处理群消息"""
        await self.process_empty_message(ctx)

    @handler(NormalMessageResponded)
    async def on_normal_message_responded(self, ctx: EventContext):
        """处理普通消息响应"""
        self.host.ap.logger.debug(f"[LarkEnhance] 处理普通消息响应: {ctx.event.response_text}")
        if not ctx.event.response_text:
            return
        
        # 取得适配器对象
        adapter = ctx.event.query.adapter
        # 如果适配器不是飞书，则不进行处理
        if not isinstance(adapter, LarkAdapter):
            return

        processed_text = ctx.event.response_text

        if not processed_text.strip():
            return
        
        # 先处理 markdown 内容
        processed_text = self.convert_mermaid_to_link(processed_text)
        processed_text = self.clean_markdown_code_blocks(processed_text)
        processed_text = self.convert_markdown_images_to_links(processed_text)
        # 处理闭合的think标签（只移除闭合标签和其内容）
        processed_text = self.remove_tags_content(processed_text)
        
        if processed_text.strip():
            ctx.add_return("reply", [processed_text])

    def convert_mermaid_to_link(self, text: str) -> str:
        """
        将Mermaid代码块转换为链接形式
        例如: ```mermaid\ngraph TD\nA-->B\n``` -> [流程图](https://yourmermaidparser.com/mermaid/code=base64encoded)
        """
        self.host.ap.logger.debug(f"[LarkEnhance] 转换Mermaid前的文本: {text}")
        def encode_mermaid(match):
            mermaid_content = match.group(1).strip()
            encoded_content = quote(base64.b64encode(mermaid_content.encode('utf-8')).decode('utf-8'))
            url = f"https://yourmermaidparser.com/mermaid/?base64={encoded_content}"
            return f'\n[流程图](https://applink.feishu.cn/client/web_url/open?mode=sidebar-semi&max_width=800&reload=false&url={url})\n'

        # 匹配mermaid代码块，支持任意空白字符
        pattern = r'```mermaid\s*(.*?)\s*```'
        result = re.sub(pattern, encode_mermaid, text, flags=re.DOTALL)
        self.host.ap.logger.debug(f"[LarkEnhance] 转换Mermaid后的文本: {result}")
        return result

    def __del__(self):
        """插件卸载时触发"""
        if hasattr(self, 'host'):
            self.host.ap.logger.info("[LarkEnhance] 插件已卸载") 