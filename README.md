# 加尔小助手

NRC（洛克王国：世界）实时 OCR 精灵检测辅助工具。通过截图 + 本地 OCR 识别游戏画面中的精灵特性与种类，以透明浮窗叠加在游戏界面上方展示结果。

## 功能

- **当前特性** — 实时识别对话框中的精灵特性（奇袭、亲密、灵巧等）
- **当前正战斗精灵种类** — 实时识别战斗中遇到的精灵种类（异色、污染、奇异、混乱等）
- **精灵种类统计** — 累计各类精灵遇到次数
- **全屏 / 窗口化自适应** — 自动检测游戏模式，区域百分比坐标精确对齐
- **Windows DPI 缩放适配** — 无视系统缩放设置，物理像素级定位
- **2.5 秒 battle 冷却** — 识别到内容后进入冷却期，避免重复触发

## 界面预览

左侧浮窗固定在游戏画面左侧（位置通过配置文件百分比控制）：

```
┌──────────────────┐
│  重置          ✕  │
├──────────────────┤
│  当前特性          │
│    奇袭            │
├──────────────────┤
│  当前正战斗精灵种类 │
│    异色精灵        │
├──────────────────┤
│  精灵种类          │
│    奇异    ×3     │
│    混乱    ×1     │
│    污染    ×2     │
│    异色    ×1     │
└──────────────────┘
```

## 配置

编辑 `check.json`：

```json
{
  "name": "NRC-Win64-Shipping.exe",
  "config": {
    "info":    { "top": ["59","91"], "left": ["0","12"] },
    "dialog":  { "top": ["76","87"], "left": ["33","65.5"] },
    "battle":  { "top": ["14","19"], "left": ["66","100"] },
    "banner":  { "top": ["11","18"], "left": ["35","64"] }
  },
  "dialog": [
    { "specialty": "奇袭", "include_content": "背部" }
  ],
  "battle": [
    { "specialty": "异色精灵", "include_content": "异色" }
  ]
}
```

- `name` — 游戏窗口标题或进程名（用于定位窗口）
- `config` — 四个区域的百分比坐标
  - `info` — 浮窗自身的位置和大小
  - `dialog` / `battle` / `banner` — OCR 识别区域
- `dialog` / `battle` — 匹配规则，`include_content` 包含即命中
- `top` / `left` — `[起始%, 结束%]`，相对于游戏画面区域

## 运行

### 开发环境

```bash
pip install -r requirements.txt
python main.py
```

### Debug 模式

```bash
# 代码内 DEBUG = True，或命令行加 --debug
python main.py --debug
```

开启后会在游戏画面上显示灰色半透明矩形标记 OCR 识别区域，控制台输出每次识别到的文字。

### 打包好的 exe

直接双击 `加尔小助手.exe` 即可运行。无需安装 Python 或下载模型。

## 打包

```bash
pip install pyinstaller
python build_exe.py
```

输出 `dist/加尔小助手.exe`，约 135MB。内含：
- RapidOCR（ONNX 中文识别模型）
- ONNX Runtime
- PySide6 界面框架
- 所有 Python 代码和配置文件

## 技术栈

| 组件 | 用途 |
|------|------|
| RapidOCR + ONNX Runtime | 纯本地中文 OCR，无需联网 |
| PySide6 | 透明浮窗 UI |
| pywin32 | 窗口截图、物理像素定位 |
| PyInstaller | 打包为单文件 exe |

OCR 模型使用 PaddleOCR 的轻量 ONNX 版本，首次运行无需下载，全部内置于 exe 中。

## 系统托盘

系统托盘右键菜单：
- **显示 / 隐藏** — 切换浮窗可见性
- **重置统计** — 清零所有累计计数
- **退出** — 关闭程序

## License

MIT
