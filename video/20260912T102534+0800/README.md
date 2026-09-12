# The Weekend Protocol / 周末交接

为 **hermes on herdr** 制作的双语产品短片：你定方向，Hermes 作为 M2 管理 Herdr，Herdr 管理天才工程师伙伴。把周末还给自己。

两版均为 **109 秒、1920 × 1080、30 fps、16:9**，H.264 / AAC，带画面内字幕。镜头、3D 动作、音乐和时间线一致，旁白、字幕和画面文字分别本地化。规格与实际检查过的 WB Beacon、Raven 成片一致；所有场景原生按此比例制作。

## 成片与配套文件

| 交付 | 中文 | English |
| --- | --- | --- |
| 最终 MP4 | [中文配音版](public/review/hermes-on-herdr-weekend-zh.mp4) | [English narration](public/review/hermes-on-herdr-weekend-en.mp4) |
| 字幕 | [SRT](public/audio/narration-zh.srt) · [VTT](public/audio/narration-zh.vtt) | [SRT](public/audio/narration-en.srt) · [VTT](public/audio/narration-en.vtt) |
| 旁白文本 | [中文](public/audio/narration-zh.md) | [English](public/audio/narration-en.md) |
| 封面 | [PNG](public/review/poster-zh.png) | [PNG](public/review/poster-en.png) |
| 实际 MP4 抽帧 | [Contact sheet](public/review/decoded-contact-zh.jpg) | [Contact sheet](public/review/decoded-contact-en.jpg) |
| 幻灯片 | [PDF](public/slides/hermes-weekend-zh.pdf) · [ODP](public/slides/hermes-weekend-zh.odp) | [PDF](public/slides/hermes-weekend-en.pdf) · [ODP](public/slides/hermes-weekend-en.odp) |
| 演讲者备注 | [中文](public/slides/speaker-notes-zh.md) | [English](public/slides/speaker-notes-en.md) |

幻灯片每版 10 页，直接使用完整镜头帧；ODP 备注可编辑，画面为光栅图，不是可编辑的 3D 对象。视频文件通过普通 Git 保存；实际字节数、SHA-256、媒体参数和验收结果见 [验证报告](verification/REPORT.md)、[media.json](verification/media.json) 与 [run.json](run.json)。

## 打开网站或 Remotion Studio

在本目录执行。需要 Node.js 22.12+、Bun；完整的实测工具版本见 [toolchain.json](verification/toolchain.json)。

```sh
cd video/20260912T102534+0800
bun install --frozen-lockfile
bun run dev
```

网站：<http://127.0.0.1:7430/>。它提供双语成片、相同位置切换语言、章节跳转、实时 3D composition，以及视频、字幕、PDF 和 ODP 下载。

```sh
bun run studio
```

Remotion Studio：<http://localhost:7431/>，composition ID 为 `HermesWeekendZH`、`HermesWeekendEN`。

## 从已提交的音轨重新渲染

需要 `ffmpeg` / `ffprobe` 和 Chrome。macOS 自动使用已安装的 Google Chrome；其他位置可通过 `CHROME_PATH` 指定。未指定且未找到系统 Chrome 时，由 Remotion 管理它的浏览器。依赖安装后，重渲染使用仓库内的本地字体、图片和音轨，不调用 TTS 服务，也不需要下载语音模型。

```sh
bun run lint
bun run typecheck
bun run test
bun run stills
RENDER_CONCURRENCY=4 bun run render
```

`bun run render zh` 或 `bun run render en` 只生成对应版本。`RENDER_CONCURRENCY` 默认 3，可根据内存和 GPU 降低。渲染先生成 3270 帧的画面，再将已母带处理的双语 AAC 混音无损封装进 MP4；没有拉伸或截短配音。

Python 工具负责字体子集、声音、幻灯片和媒体验收。安装本项目的固定依赖后运行：

```sh
uv venv .venv --python 3.12
uv pip sync --python .venv/bin/python requirements.lock
bun run slides
bun run verify
bun run build
bun run preview
```

构建后的网站在 <http://127.0.0.1:7432/>。在另一个终端运行 `bun run review`，检查真实 MP4 播放、解码音频信号、字幕解析、HTTP Range、全部章节、双语切换、实时 3D、下载内容哈希，以及 390 px 布局。`bun run review http://127.0.0.1:7430` 可检查开发站点。

`bun run verify` 会完整解码两支 MP4，检查分辨率、帧数、时长、声道、黑帧、静音区间和响度，并从实际视频抽帧与源画面对照。它也检查音频、字幕时间线和幻灯片文件哈希。阈值与实测值均在报告中公开，不把 ASR 结果冒充人工试听。

## 修改故事与重新生成声音

1. 编辑 [src/story.json](src/story.json)：双语旁白、画面文字、镜头描述、产品事实来源和固定模型版本在这里。
2. 如需改变视觉，编辑 [World.tsx](src/art/World.tsx)、[textures.ts](src/art/textures.ts) 和 [Film.tsx](src/Film.tsx)。所有运动由帧号驱动；ThreeCanvas 始终覆盖完整画幅，镜头移动通过相机完成。
3. 依次执行下列命令，再运行上面的媒体与浏览器验收。

```sh
bun run format
bun run fonts
bun run voice
bun run sound
bun run stills
bun run sample
bun run render
bun run slides
bun run verify
bun run build
```

`voice` 首次会下载固定 revision 的 Kokoro 模型到 `.cache/tts/`，此后重用；每句 WAV 都带相邻的来源和哈希 JSON。场景长度采用两种语言中较长的实测录音并留出呼吸与结尾停留，因此不会为固定时长强行裁剪声音。英文发音脚本中的 `M two` / `T U I` 用于指导发音，发布字幕自动恢复为 `M2` / `TUI`。

仅修改画面文案、未修改旁白时，可运行 `.venv/bin/python scripts/narrate.py --timing-only` 刷新故事哈希和字幕；旁白变化时此命令会拒绝旧声音。字体新增字符仍需执行 `bun run fonts`。导出图像或时间线变化后，应重新导出幻灯片。

Apple Silicon 上可选运行 `uv run scripts/asr_check.py`，对纯旁白 stem 做独立 Whisper 转写。ASR 只辅助发现疑点；品牌词、中文同音字及长静音可能误识别，原始脚本和逐句合成记录才是字幕来源。

## 制作依据与许可

- [脚本、storyboard、镜头表和功能边界](research/storyboard.md)
- [真实 WB Beacon / Raven 工程与 Hexly 品牌参考](research/references.md)，含源工程位置和成片哈希
- [完整许可清单](LICENSES.md)，包括模型发布者的原文声明、固定版本、OFL 字体与官方 Hexly 资产来源
- [Herdr Grok 审查](research/grok-review.md)与[集成决定](research/review-decisions.md)
- [验证报告](verification/REPORT.md)

旁白使用本地 **Kokoro** 合成：中文 `zf_001`、英文 `af_heart`。采用发布者 Apache-2.0 模型许可及其明确的生产／商业部署声明，保留原始许可证据；没有抓取或克隆身份不明的人声，也没有复用参考视频的 Edge TTS 音频。音乐与 3D / CLI 场景为本次原创。TUI 为仓库已有的离线演示截图，消息往来明确标为示意。

M2 是管理关系的比喻；实际运行使用当前机器上的专用、受信任 Profile，拥有完整 Herdr 控制权限。启动遵守运行意图，暂停会保持；远程跟进要求 Hermes 消息平台已配置、本机与 Herdr 在线。片中没有把未实现的向导或未验证的冷启动流程包装成已上线功能。

## 目录与存储

`src/` 是唯一渲染源，`public/` 包含可播放交付及本地资产，`scripts/` 提供复现命令，`research/` 保存剧本和来源，`verification/` 保存验收，`process/` 保留首次视觉 checkpoint、修改记录和短转场样片。`run.json` 记录本次生产与最终文件。

所有生产文件都在当前仓库；外部参考工程不参与构建。`node_modules/`、`.venv/`、`.cache/`、重复的网站 bundle、Remotion 临时 bundle 和未混音 raw MP4 均被 Git 忽略。保留可复现源、逐句语音、原创音乐 master、最终视频与有用的审查证据，避免提交模型和巨大中间缓存。
