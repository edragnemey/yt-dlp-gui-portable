# YtDlpGUI Portable

一个适用于 Windows 的简洁中文 yt-dlp 图形界面。发布包内置 yt-dlp、FFmpeg、FFprobe 和 Deno；目标电脑不需要安装 Python，也不需要配置环境变量，解压后双击即可运行。

## 功能

- 下载单个视频或完整播放列表
- 最佳画质，或限制最高 2160p / 1440p / 1080p / 720p / 480p
- MP4 兼容模式
- 提取 MP3 / M4A 音频
- 使用 FFmpeg 自动合并视频和音频
- 写入元数据和缩略图
- 实时显示进度、速度、剩余时间和日志
- 支持 Chrome、Edge、Firefox Cookie
- 一键检查 yt-dlp 更新
- 自动保存常用设置

## 直接使用

1. 打开仓库右侧的 **Releases**。
2. 下载 `YtDlpGUI-v*-windows-x64.zip`。
3. 解压整个 ZIP；不要只单独取出 EXE。
4. 双击 `YtDlpGUI.exe`。

便携包目录结构：

```text
YtDlpGUI-v1.1.0-windows-x64/
├── YtDlpGUI.exe
├── README.txt
├── THIRD_PARTY_NOTICES.txt
├── LICENSES/
└── tools/
    ├── yt-dlp.exe
    ├── ffmpeg.exe
    ├── ffprobe.exe
    └── deno.exe
```

## YouTube 登录验证

如果 YouTube 提示登录或确认不是机器人，请在界面的“浏览器 Cookie”中选择已经登录 YouTube 的 Chrome、Edge 或 Firefox，然后重试。Cookie 只由本机的 yt-dlp 读取，不会经过本项目的服务器。

## 从源码运行

需要 Python 3.10 或更高版本：

```powershell
python src/yt_dlp_gui.py
```

开发模式仍需要系统中存在 yt-dlp；FFmpeg 与 Deno 建议安装。发布包则将这些工具放在程序旁边的 `tools` 目录。

## 构建便携包

在 Windows PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-portable.ps1
```

构建脚本要求本机可通过 `PATH` 找到 `yt-dlp`、`ffmpeg`、`ffprobe` 和 `deno`。GitHub Actions 的 Release 工作流会自动下载这些依赖并构建发布包。

## 法律与使用说明

请只下载你有权保存的内容，并遵守网站服务条款以及当地法律。GUI 源代码采用 MIT 许可证；发行包内的第三方程序各自采用其原始许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
