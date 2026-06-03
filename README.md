# 五子棋 AI

基于 Python 和 Pygame 开发的五子棋对战程序，支持人机对战、双人对战、禁手规则、AI 难度选择和局面评估控制台。

## 功能特性

- 图形界面：使用 `pygame` 绘制棋盘、棋子、提示信息和难度菜单。
- 人机对战：内置五子棋 AI，支持玩家选择先手或后手。
- 双人对战：支持本地双人轮流落子。
- AI 算法：使用 Minimax、Alpha-Beta 剪枝和 VCF 算杀逻辑。
- 性能优化：使用 `numpy` 和 `numba` 加速局面评估。
- 禁手规则：可在开局前切换黑棋长连、三三、四四禁手判断。
- 评估控制台：显示当前局面评分和历史手顺得分。

## 运行环境

- Python 3.13
- `pygame`
- `numpy`
- `numba`

安装依赖：

```bash
pip install -r requirements.txt
```

运行程序：

```bash
python main.py
```

## 操作说明

- 左键：落子
- 右键：悔棋
- `A`：开局前切换玩家先后手
- `B`：人机模式下请求 AI 辅助落子
- `C`：显示或隐藏评估控制台
- `D`：开局前开启或关闭禁手规则
- `E`：开局前切换人机/双人模式
- `F`：人机模式下打开 AI 难度菜单

## 打包说明

项目使用 PyInstaller 打包，配置文件为 `五子棋.spec`。程序启动时会自动检测用户系统中可用的中文字体；如果没有匹配字体，会回退到 Pygame 默认字体。

打包命令：

```bash
pyinstaller 五子棋.spec
```

打包产物默认生成在 `dist/` 目录。

## 项目结构

```text
.
├── main.py          # Pygame 界面与游戏主循环
├── chess_ai.py      # AI 搜索、评估和禁手判断
├── requirements.txt # Python 依赖版本
├── 五子棋.spec      # PyInstaller 打包配置
└── README.md        # 项目说明
```
