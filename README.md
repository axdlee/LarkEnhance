# LarkEnhance

飞书消息增强插件，用于增强LangBot中飞书消息的处理能力。

## 安装

配置完成 [LangBot](https://github.com/RockChinQ/LangBot) 主程序后即可到插件管理页面安装  
或查看详细的[插件安装说明](https://docs.langbot.app/plugin/plugin-intro.html#%E6%8F%92%E4%BB%B6%E7%94%A8%E6%B3%95)

## 功能

本插件增强了飞书消息的处理能力，主要包含以下功能：

1. Markdown图片语法转换
   - 将Markdown格式的图片语法转换为文本链接格式以支持在飞书里点击预览
   - 例如: `![image](http://example.com/image.jpg)` -> `[参考图](http://example.com/image.jpg)`

2. Markdown代码块清理
   - 移除Markdown代码块的标记
   - 例如: \```markdown\nxxx\n\``` -> \nxxx\n
   - 其他语言的代码块（如\```python）保持不变
   - 
3. Mermaid代码块语法转换
   - 将Mermaid格式的代码块转换为文本链接格式以支持在飞书里点击预览
   - 
4. 空消息处理
   - 处理空消息的情况
   - 如果消息内容为空且存在引用消息，则使用引用消息的原文作为输入

## 使用方法

1. 将插件目录复制到 LangBot 的 plugins 目录下
2. 重启 LangBot
3. 在 WebUI 中启用插件

## 配置项

本插件无需配置，开箱即用。

## 注意事项

1. 本插件会自动处理所有飞书消息
2. 不会影响其他平台的消息处理
3. 所有处理都是自动进行的，无需用户干预

## 版本历史

- v0.1: 初始版本
  - 实现基本的消息增强功能
  - 支持Markdown图片语法转换
  - 支持多层Markdown代码块转文本
  - 支持空消息处理

## 作者

axdlee 