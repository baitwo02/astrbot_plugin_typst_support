import typst
import tempfile
import base64
import asyncio
import re
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

# =================================================================
# 不同渲染模式的模板
# 你可以在这里添加或修改模板
# `{code}` 占位符会被用户的输入内容替换
# =================================================================

# 用于通用 Typst 代码的默认模板
TEMPLATE_TYP = """
#import "@preview/physica:0.9.3": *
#set page(
    width: auto,
    height: auto,
    margin: (x: 4pt, y: 8pt)
)

{code}
"""

# 用于数学公式的模板
TEMPLATE_TYM = """
#import "@preview/physica:0.9.3": *
#set page(
    width: auto,
    height: auto,
    margin: (x: 4pt, y: 8pt)
)
#set text(size: 18pt)

$ {code} $
"""

# 用于 "OurChat" 风格的模板
TEMPLATE_YAU = """
#import "@preview/ourchat:0.2.0" as oc
#import oc.themes: *
#set page(margin: auto, height: auto, width: auto)
#let yau = wechat.default-user(name: [丘成桐（囯內）])

#wechat.chat(
  theme: "dark",
  ..oc.with-side-user(
    left,
    yau,
    oc.time[5月16日 上午10:23],
    oc.free-message[
      {code}
    ],
)

"""

# 将关键词映射到对应模板的字典
TEMPLATES = {
    "typ": TEMPLATE_TYP,
    "tym": TEMPLATE_TYM,
    "yau": TEMPLATE_YAU,
}

@register(
    "typst_support",
    "baitwo02",
    "一个将 Typst 代码片段渲染成图片的插件。",
    "1.0.0",
    "https://github.com/baitwo02/astrbot_plugin_typst_support"
)
class TypstSupportPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def _compile_and_encode(self, code: str, template: str) -> str:
        """
        使用模板编译 Typst 代码并返回 base64 编码的图片。

        Args:
            code: 用户提供的 Typst 代码。
            template: 用于包装代码的模板字符串。

        Returns:
            渲染出的 PNG 图片的 base64 编码字符串。

        Raises:
            asyncio.TimeoutError: 如果渲染过程耗时过长。
            FileNotFoundError: 如果没有生成输出图片。
            Exception: 其他渲染错误。
        """
        # 使用所选模板格式化代码
        wrapped_code = template.format(code=code)

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.typ"
            output_file = Path(tmpdir) / "output.png"
            input_file.write_text(wrapped_code, encoding='utf-8')

            # 在单独的线程中运行阻塞的编译函数
            await asyncio.to_thread(
                typst.compile,
                input_file,
                output_file,
                format="png",
                ppi=300 # 使用合理的分辨率以保证图片质量
            )

            if not output_file.exists():
                raise FileNotFoundError("编译器没有生成输出文件。")

            # 读取生成的图片并进行 base64 编码
            with open(output_file, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        """
        处理所有消息，检查是否包含 Typst 渲染关键词。
        """
        msg = event.message_str.strip()

        # 创建一个正则表达式来匹配任何一个关键词
        # 这允许更灵活的格式，例如 "typ  code"（包含多余的空格）
        keyword_pattern = r'^(?P<keyword>' + '|'.join(TEMPLATES.keys()) + r')\s+(?P<code>.+)'
        match = re.match(keyword_pattern, msg, re.DOTALL)

        if not match:
            return # 如果消息不匹配我们的格式，则不进行任何操作

        keyword = match.group('keyword')
        code = match.group('code').strip()
        template = TEMPLATES.get(keyword)

        if not code:
            yield event.plain_result(f"请在 `{keyword}` 命令后提供需要渲染的代码。")
            return

        try:
            # 为整个渲染过程设置超时
            logger.info(f"正在使用关键词 '{keyword}' 渲染 Typst 代码...")
            base64_image = await asyncio.wait_for(
                self._compile_and_encode(code, template),
                timeout=30.0
            )

            # 将图片发送给用户
            yield event.chain_result([Comp.Image.fromBase64(base64_image)])
            logger.info("成功渲染并发送 Typst 图片。")

        except asyncio.TimeoutError:
            logger.warning("Typst 渲染超时。")
            yield event.plain_result("渲染超时，请尝试简化你的代码。")
        except FileNotFoundError as e:
            logger.error(f"渲染失败：未找到输出文件。错误: {e}")
            yield event.plain_result(f"渲染失败：无法找到输出图片。")
        except Exception as e:
            # 捕获 typst 编译器可能抛出的其他错误
            logger.error(f"Typst 渲染过程中发生未知错误: {e}")
            # 清理错误信息，避免发送可能敏感的信息
            error_message = str(e).splitlines()[-1]
            yield event.plain_result(f"发生错误: {error_message}")

    async def terminate(self):
        """
        当插件被卸载或停用时调用。
        """
        logger.info("Typst 渲染插件正在终止。")

