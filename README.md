# astrbot plugin typst support

添加了 tyspt 支持，将预定义模板渲染为图片

## 模板

普通模式，触发关键字为`typ`
```typst
#set page(
    width: auto,
    height: auto,
    margin: (x: 5pt, y: 10pt)
)
#set text(size: 16pt, font: {font_stack})

{code}
```

数学模式，触发关键字为`tym`
```typst
#import "@preview/physica:0.9.3": *
#set page(
    width: auto,
    height: auto,
    margin: (x: 4pt, y: 8pt)
)
#set text(size: 18pt, font: {font_stack})

$ {code} $
```

yau模式，触发关键字为`yau`
```typst
#import "@preview/ourchat:0.2.0" as oc
#import oc.themes: *
#set page(margin: auto, height: auto, width: auto)
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
```

## 用法
在句子前面加上关键字即可，例如`yau 我没有说过这种话`

## TODO
- [ ] 添加自定义模板功能
- [ ] yau模式添加实时时间

## 注意

如果提示：
```
[Plug] [ERRO] [astrbot_plugin_typst_support.main:167]: Typst 渲染过程中发生未知错误: file not found (searched at /root/.cache/typst/packages/preview/ourchat/0.2.0/src/assets/discord-newbie.svg)
```
可以尝试手动克隆仓库并导入资源：
```
git clone https://github.com/QuadnucYard/ourchat-typ.git
podman cp /home/baitwo02/service/ourchat-typ/src/assets astrbot:/root/.cache/typst/packages/preview/ourchat/0.2.0/src/
```

# 支持

[帮助文档](https://astrbot.app)
