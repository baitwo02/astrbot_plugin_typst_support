import typst
import tempfile
import base64
import asyncio
import re

from pathlib import Path
from opencc import OpenCC

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

# =================================================================
# 模板定义
# =================================================================

# 定义字体组合 (Font Stack)
# 简体中文栈
SC_FONT_STACK_TUPLE = ("Liberation Serif", "Source Han Serif SC")
# 繁体中文栈
TC_FONT_STACK_TUPLE = ("Liberation Serif", "Source Han Serif TC")

# 通用模板
TEMPLATE_TYP = """
#set page(
    width: auto,
    height: auto,
    margin: (x: 5pt, y: 10pt)
)
#set text(size: 16pt, font: {font_stack})

{code}
"""

# 数学公式模板
TEMPLATE_TYM = """
#import "@preview/physica:0.9.3": *
#set page(
    width: auto,
    height: auto,
    margin: (x: 4pt, y: 8pt)
)
#set text(size: 18pt, font: {font_stack})

$ {code} $
"""

# "OurChat" 风格模板
TEMPLATE_YAU = """
#import "@preview/ourchat:0.2.0" as oc
#import oc.themes: *
#set page(margin: 0pt, height: auto, width: auto)
#set text(font: {font_stack})
#let yau = wechat.default-user(name: [丘成桐（囯內）])

#wechat.chat(
  theme: "light",
  ..oc.with-side-user(
    left,
    yau,
    oc.time[5月16日 上午10:23],
    oc.free-message[
      {code}
    ],
  ),
)
"""

# 将关键词映射到对应模板的字典
TEMPLATES = {
    "typ": TEMPLATE_TYP,
    "tym": TEMPLATE_TYM,
    "yau": TEMPLATE_YAU,
}

@register(
    "astrbot_plugin_typst_support",
    "baitwo02",
    "添加 typst 渲染支持",
    "1.2.2",
    "https://github.com/baitwo02/astrbot_plugin_typst_support"
)
class TypstSupportPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_dir = Path(__file__).parent.resolve()
        base_font_dir = self.plugin_dir / "fonts"
        
        # 更新字体路径
        self.font_paths = [
            str(base_font_dir / "liberation-fonts-ttf"),
            str(base_font_dir / "source-han-serif-otf")
        ]
        logger.info(f"Typst 插件已加载，字体目录设置为: {self.font_paths}")
        for path in self.font_paths:
            if not Path(path).exists():
                logger.warning(f"字体路径不存在！请检查: {path}")

        # 分别为简繁创建 Typst 格式的字体栈字符串
        sc_quoted_fonts = [f'"{font}"' for font in SC_FONT_STACK_TUPLE]
        self.sc_typst_font_stack_str = f'({", ".join(sc_quoted_fonts)})'
        logger.info(f"Typst 简体字体栈已配置为: {self.sc_typst_font_stack_str}")
        
        tc_quoted_fonts = [f'"{font}"' for font in TC_FONT_STACK_TUPLE]
        self.tc_typst_font_stack_str = f'({", ".join(tc_quoted_fonts)})'
        logger.info(f"Typst 繁体字体栈已配置为: {self.tc_typst_font_stack_str}")

        # 初始化简繁转换器 (s2t: Simplified to Traditional)
        self.cc = OpenCC('s2t.json')
        logger.info("OpenCC (s2t) 转换器已初始化。")


    async def _compile_and_encode(self, code: str, template: str, font_stack_str: str) -> str:
        """
        使用模板编译 Typst 代码并返回 base64 编码的图片。
        """
        wrapped_code = template.format(font_stack=font_stack_str, code=code)

        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.typ"
            output_file = Path(tmpdir) / "output.png"
            input_file.write_text(wrapped_code, encoding='utf-8')

            await asyncio.to_thread(
                typst.compile,
                input_file,
                output_file,
                format="png",
                ppi=300,
                font_paths=self.font_paths
            )

            if not output_file.exists():
                raise FileNotFoundError("编译器没有生成输出文件。")

            with open(output_file, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        """
        处理所有消息，检查是否包含 Typst 渲染关键词。
        """
        msg = event.message_str.strip()
        keyword_pattern = r'^(?P<keyword>' + '|'.join(TEMPLATES.keys()) + r')\s+(?P<code>.+)'
        match = re.match(keyword_pattern, msg, re.DOTALL)

        if not match:
            return

        keyword = match.group('keyword')
        code = match.group('code').strip()
        template = TEMPLATES.get(keyword)
        
        font_to_use = self.sc_typst_font_stack_str # 默认使用简体字体栈

        # 如果是 yau 模式，则将 code 转换为繁体中文，并切换到繁体字体栈
        if keyword == 'yau':
            original_code = code
            code = self.cc.convert(original_code)
            font_to_use = self.tc_typst_font_stack_str # 切换字体栈
            logger.info(f"YAU 模式：已将 '{original_code}' 转换为 '{code}'，使用繁体字体栈。")

        if not code:
            yield event.plain_result(f"请在 `{keyword}` 命令后提供需要渲染的代码。")
            return

        try:
            logger.info(f"正在使用关键词 '{keyword}' 渲染 Typst 代码...")
            base64_image = await asyncio.wait_for(
                self._compile_and_encode(code, template, font_to_use),
                timeout=30.0
            )
            yield event.chain_result([Comp.Image.fromBase64(base64_image)])
            logger.info("成功渲染并发送 Typst 图片。")

        except asyncio.TimeoutError:
            logger.warning("Typst 渲染超时。")
            yield event.plain_result("渲染超时，请尝试简化你的代码。")
        except FileNotFoundError as e:
            logger.error(f"渲染失败：未找到输出文件。错误: {e}")
            yield event.plain_result(f"渲染失败：无法找到输出图片。")
        except Exception as e:
            logger.error(f"Typst 渲染过程中发生未知错误: {e}")
            error_message = str(e).splitlines()[-1]
            yield event.plain_result(f"发生错误: {error_message}")

    async def terminate(self):
        """
        当插件被卸载或停用时调用。
        """
        logger.info("Typst 渲染插件正在终止。")
