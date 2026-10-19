# AudioScribe Mac preview 1 验证记录

验证日期：2026-10-19。环境：Apple Silicon、macOS 26.5.2、Google Chrome。

## 已验证

- 22 项 Python 测试通过，包括 7 项 Mac 适配测试。
- 验证本地安装、路径含空格时的运行、Native Messaging 消息与断开清理。
- Chrome 实际导入含英文语音的 MP4，完成本地转写与关键词会议草稿。
- 通过界面分别导出 TXT、DOCX、SRT；检查 TXT/SRT 内容及 DOCX 内部 document.xml。
- 本次未进行 Microsoft Word 中的 DOCX 视觉排版验收。

## 测试边界

本构建面向 Apple Silicon / macOS 14+；实际验收运行于 macOS 26.5.2，未覆盖所有受支持系统版本。未覆盖 Intel、Chrome Beta/Canary、Edge、Safari。安装流程通过命令行执行并在真实 Chrome 中验证；未完成全新机器下载后双击安装器 GUI 的完整验收。

安装器尚未使用 Developer ID 签名或公证。首次模型下载依赖网络；本次成功的本地语音样本测试不能保证所有网络环境下的下载成功率。

尚未验证长录音、噪声或重叠发言、多语言识别以及 Ollama 会议整理。自动转写和会议草稿需人工核对。

## 构建与依赖

构建方法见 [README](README.md)，精确依赖见 `requirements.lock`，运行时来源及校验值见 `runtime-sources.json`。发行包保留第三方许可证与依赖元数据。
