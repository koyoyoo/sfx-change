# sfx-change

一个基于 ffmpeg 的批量音频转换工具：递归扫描目录中的 `.ogg` 文件，并批量输出为 `.wav`。

## 特性

- 提供桌面可视化界面与命令行两种使用方式
- 递归批量转换，支持单个文件或整个目录
- 默认在原文件旁生成同名 WAV，也可输出到独立目录
- 输出目录可选择保留或忽略原始目录层级
- 多文件并发转换
- 支持覆盖、采样率、声道数和 dry-run 预览
- 仅依赖 Python 标准库与本机 ffmpeg

## 安装

先安装 ffmpeg：

```bash
# Ubuntu / Debian
sudo apt install ffmpeg python3-tk

# macOS（Homebrew）
brew install ffmpeg
```

然后安装本工具：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell 可使用：

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## 可视化界面

### Windows 免安装启动（推荐）

无需 `pip install`，在仓库根目录直接运行：

```powershell
.\ogg2wav-gui.cmd
```

### 已安装命令行启动

先按上一节创建虚拟环境并执行 `pip install -e .`，然后启动：

```bash
# macOS / Linux
ogg2wav-gui
```

```powershell
# Windows PowerShell（已激活 .venv）
ogg2wav-gui

# 如果没有激活虚拟环境，也可以直接运行
.\.venv\Scripts\ogg2wav-gui.exe
```

### 源码启动

```bash
# macOS / Linux
PYTHONPATH=src python -m sfx_change.gui
```

```powershell
# Windows PowerShell
$env:PYTHONPATH="src"; python -m sfx_change.gui; Remove-Item Env:PYTHONPATH
```

界面中可多选输入文件或选择目录、设置输出目录与转换选项，点击“开始转换”即可；输出目录留空时会在原 OGG 文件旁生成 WAV。若系统 `PATH` 中没有 ffmpeg，但已安装 `imageio-ffmpeg` Python 包，界面会自动使用其内置 ffmpeg。

## 命令行使用

转换目录中的所有 OGG，并在原文件旁生成 WAV：

```bash
ogg2wav ./audio
```

转换到独立目录，并保留原始目录层级：

```bash
ogg2wav ./audio -o ./wav-output
```

平铺输出、8 路并发、覆盖已有文件：

```bash
ogg2wav ./audio -o ./wav-output --flat -j 8 --overwrite
```

指定 48 kHz 采样率和立体声：

```bash
ogg2wav ./audio -o ./wav-output --sample-rate 48000 --channels 2
```

只预览转换清单，不实际转换：

```bash
ogg2wav ./audio -o ./wav-output --dry-run
```

查看完整参数：

```bash
ogg2wav --help
```

也可以不安装，直接从源码运行：

```bash
PYTHONPATH=src python -m sfx_change ./audio -o ./wav-output
```

## 退出码

- `0`：全部成功、跳过已有文件，或未找到 OGG 文件
- `1`：至少一个文件转换失败
- `2`：输入路径、参数或 ffmpeg 不可用

## 开发

运行测试：

```bash
python -m unittest discover -s tests -v
```
