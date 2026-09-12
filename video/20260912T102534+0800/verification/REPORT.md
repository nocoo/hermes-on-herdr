# 成片验证报告

生产：**The Weekend Protocol / 周末交接**，2026-09-12。结论：双语最终成片与构建后的网站通过下列检查。完整机器结果见 [media.json](media.json)、[browser.json](browser.json)、[slides.json](slides.json) 和 [toolchain.json](toolchain.json)。

## 最终媒体

| 项目 | 中文版 | English |
| --- | --- | --- |
| 文件 | [MP4](../public/review/hermes-on-herdr-weekend-zh.mp4) | [MP4](../public/review/hermes-on-herdr-weekend-en.mp4) |
| 字节数 | 17,061,184（16.27 MiB） | 17,105,462（16.31 MiB） |
| 时长 / 帧数 | 109.000 秒 / 3270 | 109.000 秒 / 3270 |
| 视频 | H.264 · 1920 × 1080 · 30 fps · yuv420p | 相同 |
| 音频 | AAC · 48 kHz · 双声道 | 相同 |
| 最终综合响度 | −16.13 LUFS | −16.18 LUFS |
| 最终 true peak | −1.78 dBTP | −1.71 dBTP |
| 完整解码 | 无错误 | 无错误 |
| 检出的黑帧 / 异常静音区间 | 0 / 0 | 0 / 0 |

SHA-256：

```text
zh  92145345553525497b434feea96a86cf94b0c45c2c68d8b06daa017d59908be5
en  2815334497113954b712074b6948f87eb4b87763e71125f412c9477ea29b1bfe
```

## 检查方法与范围

- `ffprobe` 检查真实 MP4 的编解码器、尺寸、帧率、帧数、时长、采样率和声道；`ffmpeg -v error -i <film> -f null -` 完整解码两支视频，stderr 均为空。
- 逐帧黑场扫描：`blackdetect=d=0:pix_th=0.02:pic_th=0.98`，未发现至少 98% 像素落入黑色阈值的帧。开头保留产品标识，结尾停在品牌画面，没有淡出黑场。
- 最终混音扫描：`silencedetect=noise=-55dB:d=0.25`，没有超过 0.25 秒的异常静音区间。每句原始 WAV 另外通过 −48 dB / 0.85 秒检查，无异常长的内部停顿；40 句音频均为有效、非零、未削波的 24 kHz PCM，哈希与时间线一致。
- 每版 20 条字幕对应 20 句完整旁白，无重叠、无被镜头结尾截断的句子。英文画面字幕使用 `M2` / `TUI`，发音脚本仍可拼读这些缩写。两版保留相同镜头长度与转场。
- 最终视频各抽取 10 个完整镜头帧，与无字幕源图的顶部 860 px 比较，RGB RMSE 分别为 **2.207–2.613**、**2.179–2.616**，低于 9 的阈值；字幕区域单独视觉检查。[中文 contact sheet](../public/review/decoded-contact-zh.jpg) / [English contact sheet](../public/review/decoded-contact-en.jpg) 来自最终 MP4。
- 另外检查了英文第 1604 帧的 M2 字幕、第 2540 帧的 TUI 字幕，以及中文版 83 秒监控画面。字幕完整，位于主画面下方。命令与帧号保存在 [caption-frames.json](caption-frames.json)。
- 查看了两版最终帧：[中文](decoded-zh/last.png)、[English](decoded-en/last.png)。门形产品标识、产品名、Hexly 官方标识、hexly.ai 和仓库地址完整保留。较长版本的旁白结束后仍有 **3.87 秒**品牌停留。
- Herdr 中的 Grok 独立查看两张最终 contact sheet 和两版最终帧，未发现视觉阻断；范围和原文见 [审查记录](../research/grok-final-visual-review.md)。主协调者也查看了全部 20 个章节抽帧、修正字幕帧、结尾帧及桌面／手机网站截图。

音轨验证采用逐句 WAV 校验、整片解码、响度／静音扫描和浏览器音频采样。独立 Whisper ASR 仅辅助定位疑点：长静音和 30 秒窗口导致整轨转写出现漏词与幻觉，逐句复查确认对应英文原始句子完整；中文存在同音字与品牌拼写误识别。原始结果保存在 `asr-zh.json`、`asr-en.json`、`asr-sentence-review.json`，没有用识别结果替代正式字幕，也没有声称完成了人工试听。

## 网站、源码和幻灯片

| 检查 | 实际结果 |
| --- | --- |
| 安装 | Bun 固定依赖与 Python 3.12 lock 均已实际安装；Remotion 所有组件固定为 4.0.520 |
| `bun run lint` | 通过，15 个文件，无待修复项 |
| `bun run typecheck` | 通过 |
| `bun run test` | 3 / 3 通过，覆盖公共时间线、语音资产哈希与双语字幕对齐 |
| Python 脚本语法 | `python -m compileall -q scripts` 通过 |
| 原插件离线测试 | **167 / 167** 通过，41.919 秒；[原始日志](plugin-tests.txt) |
| `bun run build` | 通过，Vite 7.3.0，93 modules；生成可独立运行的 `website/` |
| `bun run review` | 在构建后的 `http://127.0.0.1:7432/` 通过，Chrome 152；没有页面错误、控制台错误或警告 |
| 真正播放 | 双语 MP4 均实际推进、解码视频帧，Web Audio analyser 采样到非零音频；390 px 下也实际播放后抽取页面截图 |
| 章节与语言 | 两版所有 10 个章节定位通过；83 秒处中英文互切保留位置；视频／实时 3D 切换保留位置 |
| 实时 Three.js | 初始化后 drawing buffer 为 1920 × 1080，字幕与实际时间线一致 |
| 下载与流式读取 | 8 次 MP4 / SRT / PDF / ODP 实际下载，内容 SHA-256 与仓库文件一致；双语 MP4 Range 请求返回 HTTP 206 |
| 手机布局 | 两版 390 px 视口的文档宽度均为 390 px，无水平溢出；[截图目录](browser/) |
| PDF / ODP | 每版各 10 页；PDF 中图像逐像素等于无字幕源帧；ODP 包结构、图像哈希和原生备注逐项通过 |

构建保留 Vite 对大于 500 kB chunk 的提示：Three.js / Remotion 浏览器包约 1.37 MB，gzip 391 kB。这不影响构建和播放。没有为本次宣传片引入额外代码分包架构。

插件测试命令在仓库根执行：`video/20260912T102534+0800/.venv/bin/python -I -B tests/run.py`。测试使用原有隔离 fixture，没有调用当前在线 Gateway，也没有继续旧 CI 调查。除 README 导航与忽略规则外，原插件源码、配置和测试保持原样。

## 共同镜头表

| 镜头 | 开始 | 长度 |
| --- | ---: | ---: |
| 产品片头 | 0.0 s | 3.5 s |
| 信任的工程师伙伴 | 3.5 s | 12.5 s |
| 多 Agent 的管理问题 | 16.0 s | 10.5 s |
| Herdr 管理天才 IC | 26.5 s | 10.5 s |
| 周末，谁管理 manager | 37.0 s | 8.5 s |
| 专用 Hermes 作为 M2 | 45.5 s | 12.0 s |
| 完整 Herdr 控制权限 | 57.5 s | 11.0 s |
| 生命周期与持久暂停 | 68.5 s | 12.0 s |
| monitor TUI 与远程跟进 | 80.5 s | 17.0 s |
| 周末归还与 Hexly 片尾 | 97.5 s | 11.5 s |

## 来源、范围与交付

[许可清单](../LICENSES.md) 保存 Kokoro 两版模型及 voice preset 的固定来源、Apache-2.0 许可和发布者明确的生产／商业使用声明；不将模型许可写成个人配音演员的单独授权书。配乐、3D 与 CLI 画面为本次原创；产品与 Hexly 品牌使用用户授权的官方资产；字体为 OFL。没有复制参考视频音轨或版权不明的人声。

WB Beacon 与 Raven 的真实本机工程、实际成片和来源哈希见 [参考记录](../research/references.md)。这些工程及 Hexly 仓库只读，未作修改；所有本次生产与验证文件位于当前仓库。

两支最终视频均远低于 GitHub 单文件 100 MiB 限制；本次提交没有达到 50 MB 的单文件，使用 **普通 Git**。模型缓存、虚拟环境、node_modules、网站／Remotion 重复 bundle 和 raw MP4 不进入提交。完整源、逐句语音、音乐 master、成片、字幕、幻灯片与有用审查资料随同一个原子提交交付。发布身份以本报告所在的 Git commit 为准；推送后的远端 main 提交号在最终交付回复中给出。
