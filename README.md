# 音频转文字 · AudioScribe

## Mac 测试版

已增加 Apple Silicon（M 系列）macOS 14+ 安装器和原生助手适配。使用 Mac 安装包，解压后打开安装器；不要运行 Windows EXE。内置 Python，首次仍需在 Chrome 加载扩展。构建与数据目录见 [Mac 说明](native/macos/README.md)。下载 [Mac preview 1](https://github.com/zwhzw-10/AudioScribe/releases/tag/v0.1.0-macos-preview.1)；安装步骤见 [使用说明](native/macos/USER-GUIDE.zh-CN.txt)，测试范围与限制见 [验证记录](native/macos/VALIDATION.md)。

独立的 Windows / Chrome 本地会议录音转写工具，0.1.0 测试版。与 CaptionCraft 字幕插件拥有不同的扩展 ID、助手注册和数据目录，可同时安装。

## 下载

普通用户请在 [Releases 下载完整安装包](https://github.com/zwhzw-10/AudioScribe/releases)，不要下载 Source code。

## 安装

普通用户仅需运行 **AudioScribe-Setup-v0.1.0.exe**，点击“安装助手和插件”。安装完成后点击“复制路径并打开 Chrome”，开启开发者模式 → 加载未打包的扩展程序。在文件夹窗口的地址栏粘贴路径、按回车，再点击“选择文件夹”，不要进入 icons 子文件夹。

Chrome 要求用户亲自确认加载扩展；这是减少手动步骤的完整安装包，并非静默安装。加载后点击 Chrome 的拼图图标，选择“音频转文字”，打开工作页面。插件安装文件在 `%LOCALAPPDATA%\AudioScribe`，不要移动或删除它。下载的 EXE 安装后可归档或删除。

首次转写下载所选 Whisper 模型：Tiny 大约 75 MB、Base 大约 145 MB、Small 大约 465 MB，下载缓存可能额外占用空间。模型下载源是 Hugging Face，网络不通会导致首次准备失败；已完整缓存后可离线转写。CPU int8，无需独立显卡，建议 Windows 10/11 x64、至少 8 GB 内存和 3 GB 可用磁盘空间。速度依硬件、模型和录音时长变化，不能保证实时速度。

## 功能

- MP4 / MP3 / M4A / WAV / WebM / OGG / FLAC，本地提取第一条音轨；最多 500 MB、4 小时。
- 中文、英文优先，另可选择日语、法语、西班牙语、韩语、俄语；自动识别主要语言。未验证混合语言会议质量。
- 逐段转写、进度、停止、编辑、点击时间回听。浏览器不支持的回听格式需外部播放器打开原文件。
- 默认会议记录是带时间的**关键词摘录草稿**，不是完整语义总结；否定句和讨论中的建议也可能成为“决定候选”，请核对。
- 可选连接已安装的 **Ollama 本地 GGUF 模型**做语义整理；没有 Ollama 也能完成转写、摘录和导出。模型需用户另行安装，本版不包含其安装程序或模型，不自动调用任何云端服务。建议此功能至少 16 GB 内存；仍可能遗漏或误解。长会议分段整理并保留各段结果，尚不合并全局重复待办。
- 导出编辑后的 TXT、SRT、Word DOCX。会议记录不导出 SRT，因为摘要没有独立时间轴。
- 没有自动说话人区分，不声称能识别姓名。

## 隐私与权限

文件仅发送到随机端口的本机助手，使用随机令牌及准确扩展 Origin 校验。没有 content scripts、网站读取权限、麦克风权限或云端转写 API。`nativeMessaging` 用来启动助手，localhost 权限用于传送录音和接收结果。

源录音不会被修改；临时副本在处理完成/停止后删除。进程意外终止可能留下临时音频，下一次启动会清理超过一天的临时副本。记录在内存中，离开页面前必须导出。页面“清除本次记录”清除本次文字，模型缓存保留。日志不记录录音内容或完整逐字稿，但可能包含本地错误路径。模型首次下载会连接模型仓库，仓库可看到网络请求信息。

音频中可能包含他人的隐私，使用者应确认录音和处理权限。

## 开发与验证

`extension/` 工作页面、`helper/` 本地转写与文档导出、`native/` Windows 安装及 Chrome 桥接。构建方法见 `native/build_windows.py`，需 Windows .NET Framework C# 编译器与带依赖的 Python runtime ZIP。模型权重与用户数据不打包。官方参考：[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[Ollama generate](https://docs.ollama.com/api/generate)、[Chrome Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)。

源代码及 Logo 使用 MIT；Python runtime、依赖和模型保留各自许可证。助手未数字签名，Chrome 商店尚未上架。公开商业发行前仍需模型许可证审查、真实电脑安装及多语言会议测试。

详见 TEST-REPORT.md。
