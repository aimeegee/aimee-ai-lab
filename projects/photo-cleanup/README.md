# 照片清理工具（M1 预览版 + M2 执行版）

本地运行的照片清理脚本。输入一个照片目录（含子目录），识别：

- 完全重复（字节哈希）
- 相似图片聚类（感知哈希），覆盖「原图 + 编辑/裁剪版」「原照片 + 该照片的截屏」两种配对场景
- 误拍短视频（时长阈值，默认 3 秒）
- 截图（分辨率匹配已知 iPhone 屏幕 + 无相机 EXIF）
- Live Photo 的 `.MOV` 伴生文件（不会被误判成短视频，且删除/移动图片时会跟着一起处理）

全部判断只用本地算法（字节哈希 / 感知哈希 / 视频元数据 / EXIF），**不联网、不调用任何 LLM 或视觉模型**。

三种运行模式：
- **preview**（M1）：只读扫描 + 生成报告，不删除、不移动任何文件
- **execute**（M2）：真正清理——完全重复副本移到系统回收站（不是永久删除），相似组多余项/短视频移到「待复查」，并生成一份操作记录
- **revert**（M2）：按某次 execute 生成的操作记录，把「待复查」里的文件放回原路径

## 安装

需要 Python 3.9+。

```bash
cd projects/photo-cleanup
pip install -e .
# 或者: pip install -r requirements.txt
```

`pip install -e .` 会注册一个 `photo-cleanup` 命令；也可以不装，直接用 `python3 -m photo_cleanup.cli`（需要把 `src/` 加进 `PYTHONPATH`，或者在 `projects/photo-cleanup/src` 目录下执行）。

## 运行

```bash
photo-cleanup --dir /path/to/照片目录
```

或不装包直接跑：

```bash
cd projects/photo-cleanup/src
python3 -m photo_cleanup.cli --dir /path/to/照片目录
```

跑完会在终端打印各类别数量，并在 `<照片目录的上级目录>/photo-cleanup-reports/` 下生成两份报告（JSON 给程序/agent 读，Markdown 给人读），文件名带输入目录名和时间戳，不会互相覆盖。

### 常用参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--dir` / `-d`（必填） | — | 要扫描的照片目录 |
| `--video-threshold-seconds` | `3.0` | 短视频时长阈值（秒），低于此值标记为短视频 |
| `--similarity-threshold` | `10` | 相似判定的感知哈希汉明距离阈值；数值越大越宽松，容易把不同照片归并到一组（默认偏严，见 `decisions.md` D-001） |
| `--phash-size` | `16` | 感知哈希精细度，一般不需要改 |
| `--report-dir` | 输入目录同级的 `photo-cleanup-reports/` | 报告（及 execute 的操作记录）输出目录 |
| `--review-dir` | 输入目录同级的 `<目录名>-待复查/` | 「待复查」文件夹路径（execute 模式用） |
| `--mode` | `preview` | `preview` / `execute`（M2）/ `revert`（M2） |
| `--operation-log` | — | revert 模式用：要还原的操作记录 JSON 路径；不填则自动找该目录最近一次 execute 的操作记录 |
| `--json-only` | 关 | 只写 JSON 报告，不写 Markdown |
| `--quiet` | 关 | 不在终端打印摘要 |

示例：换一批照片、调松相似判定、短视频阈值改成 2 秒：

```bash
photo-cleanup --dir ~/Documents/Photos/2026 --similarity-threshold 16 --video-threshold-seconds 2
```

### 执行模式（M2）

确认 preview 报告判得准之后，用 execute 模式真正清理：

```bash
photo-cleanup --dir ~/Documents/Photos/2025 --mode execute
```

- 完全重复的多余副本（及其 Live Photo 伴生 `.MOV`）会被移到系统回收站（macOS 的「废纸篓」），**不是永久删除**
- 相似组的多余项、被标记的短视频（及其 Live Photo 伴生 `.MOV`）会被移到「待复查」文件夹，默认在输入目录同级的 `<目录名>-待复查/` 下，按类别分子文件夹（`相似/<组号>/`、`短视频/`）
- 截图只做标记，不移动不删除，除非它同时命中完全重复或相似规则
- 每次执行会额外生成一份操作记录（`<...>_operations.json`），记录每个被删除/移动文件的原路径、去向，以及命中时的具体数值（相似组的感知哈希距离、短视频的时长秒数）
- 对同一目录再跑一次 execute 不会产生新的删除/移动（执行后组内已经只剩 1 个文件，不会再被归组）；非图片/视频文件永远不受影响

还原（把「待复查」里的文件放回原路径；已经进回收站的完全重复副本不会被还原，这是设计上的：回收站里的文件本来就该留在那里，想找回去 Finder 的废纸篓里手动拖）：

```bash
photo-cleanup --dir ~/Documents/Photos/2025 --mode revert
```

不传 `--operation-log` 时，会自动用该目录最近一次 execute 生成的操作记录；也可以用 `--operation-log <路径>` 显式指定某一次的操作记录。

## 报告里有什么

每个被命中的文件一行：原路径、类别（完全重复/相似/短视频/截图）、命中原因（相似组带感知哈希距离，短视频带时长秒数）、动作、所属组号；每个完全重复组/相似组标出保留哪个文件；末尾有分类数量汇总，汇总数与明细行数必然一致（报告结构上保证，不是另算的）。

JSON 报告里每条命中还带着「数值证据」（`phash_distance` / `duration_seconds` 等），是为以后做反馈调参（M4，待 Aimee 用过真实数据后再设计）预留的，现在就记，成本很低。

## 判定规则要点（细节见 `../requirements.md` 和 `../decisions.md`）

- **保留优先级冲突仲裁**：完全重复 > 相似 > 短视频 > 截图标记——每个文件最终只会出现在一个类别里。
- **完全重复保留规则**：文件名不带 `(1)` / `-1` / macOS 常见的` 2`（空格+数字）这类副本后缀的优先保留；都带或都不带时取文件名排序第一个。
- **相似组保留规则**：① 组内有文件名配对的编辑/裁剪版（如 `IMG_1234`/`IMG_E1234`）→ 留编辑版；② 否则组内有非截图版本 → 留非截图版本；③ 否则留像素数最多的一张，像素相同留文件更大的。
- **相似判定的两种配对场景**：
  - (a) 原图 + 编辑/裁剪版：靠文件名规则识别（`IMG_xxxx` ↔ `IMG_Exxxx`），不依赖感知哈希距离，所以即使裁剪幅度较大也能配对上。
  - (b) 原照片 + 对它的截屏：靠感知哈希识别。截屏比对时会额外算一份「去掉四周近纯色边条（状态栏/黑边/手势条）」之后的感知哈希，两张图各自的「完整画面」和「去边条画面」两两比较取最小距离——这是让截屏能跟原图匹配上的关键，否则截屏四周的系统 UI 会把距离拉得很大。这个启发式规则是用合成样本调出来的默认参数，真实照片上可能需要用 `--similarity-threshold` 微调（见「已知局限」）。
- **Live Photo**：同目录、同文件名（不含扩展名）的图片 + `.MOV` 视为一体，`.MOV` 不参与短视频判断；图片命中某规则时，`.MOV` 伴生文件会显示同样的分类/动作，execute 模式会把它和配对图片一起删除/移到同一个目标文件夹。
- **执行模式的落地位置**：完全重复的多余副本进系统回收站；相似组多余项进「待复查/相似/<组号>/」；短视频进「待复查/短视频/」；只命中截图规则的文件原地不动。

## 代码结构

```
src/photo_cleanup/
  config.py          可调参数、已知 iPhone 屏幕分辨率表
  models.py          核心数据模型（FileRecord / Hit / DuplicateGroup / ScanResult）
  naming.py          文件名规则（副本后缀、编辑版配对）
  exif_meta.py        EXIF 读取（只看 Make/Model/GPS 有没有，不做内容解读）
  video_meta.py       视频时长读取（用 OpenCV，不依赖 ffmpeg 命令行）
  screenshot_rules.py 截图判定规则
  hashing.py          字节哈希 + 感知哈希聚类（numpy 向量化，照顾大批量文件的性能）
  walker.py           扫目录、建 FileRecord、Live Photo 配对——只收集事实，不做判断
  classify.py         套用四条规则 + 优先级仲裁——只做判断，不碰文件
  report.py           生成 JSON / Markdown 报告
  fsutil.py           executor.py / trash.py 共用的小工具（目标路径去重避免覆盖）
  trash.py            把文件移到系统回收站（macOS 的 ~/.Trash），不做永久删除
  executor.py         execute 模式（真正删除/移动、写操作记录）+ revert（按操作记录还原）
  cli.py              命令行入口（preview / execute / revert 三种模式）
```

分层是故意的：`walker.py`（收集事实）和 `classify.py`（做判断）都不执行任何文件系统写操作，`models.py` 里的 `Action` 枚举定义了「删除/移至待复查/仅标记」等动作、`FileRecord`/`DuplicateGroup` 记录了「谁该留、谁该走、走到哪」。`executor.py` 只读这些结构分发动作，不碰分类逻辑；`cli.py` 的三种模式都复用同一套 `scan_directory` → `classify` 流程。

## 自测

跑验收测试（会在临时目录里生成一套合成样本集，逐条核对 requirements.md 的 AC-1 ~ AC-19）：

```bash
cd projects/photo-cleanup
python3 -m pytest tests/ -v
```

`tests/test_acceptance.py` 覆盖 AC-1~12（预览模式/识别），`tests/test_execute_acceptance.py` 覆盖 AC-13~19（执行模式/删除移动/还原/幂等），`tests/test_tester_review.py` 是 Tester 独立复核时补的回归测试。

**注意**：AC-13 相关的测试会真的把合成样本文件移进系统回收站（macOS 的 `~/.Trash`，这是 execute 模式本身的设计，没法绕过去不碰真实回收站），测试结束会自动清理掉自己丢进去的文件（见 `tests/trash_test_support.py`），不会在 `~/.Trash` 里留垃圾。

也可以单独生成样本集看一眼（不跑测试）：

```bash
python3 tests/sample_generator.py /tmp/photo-cleanup-samples
```

详细的自测结果和已知局限见 lead 的回报 / `STATUS.md`。

## 已知局限

- **截图-原照片的感知哈希匹配是启发式规则，在真实照片上没有验证过**：默认参数是用代码合成的样本调出来的（见 `tests/sample_generator.py` 里 `make_screenshot_of` 的生成方式），真实场景里截屏的构图比例、App 的 UI 样式千变万化，命中率和误判率需要拿真实数据跑过才知道；这正是 `decisions.md` D-010 里说的「先跑 M1~M3 积累数据，再设计 M4 反馈调参」的原因。
- **文件名配对规则只认 `前缀_数字` / `前缀_E数字` 这一种 iOS 命名格式**，以及 `(N)`/`-N`/` N`（macOS 常见的空格+数字）这三种副本后缀写法；如果 Aimee 的照片目录里有别的命名习惯（比如 Android 截图名、其他备份工具加的后缀），这部分规则可能需要再调整。
- **Live Photo 配对**：如果同一目录里同名（不含扩展名）同时存在多种图片格式（比如 `IMG_1234.HEIC` 和 `IMG_1234.JPG` 都在），当前实现会把同名的 `.MOV` 和两张图片都关联上，而不是只认一张；这种情况在真实 iPhone 导出目录里理论上不常见，但没有专门测试过。
- **AC-12（5000 文件 30 分钟内跑完 preview）没有在 5000 个真实文件上实测**：用 600 张代码合成的 1600×1200 JPEG 测过，扫描 + 分类共 9.1 秒，折算到 5000 张约 1.3 分钟，有约 20 倍余量；但真实 HEIC 照片（iPhone 拍摄通常是 3000万像素级、体积更大）解码和视频读取的耗时会比合成样本更高，没有在 Aimee 的真机环境上跑过 5000 个真实文件验证。
- **本工具本身没有做过"断网"的实测**：已经用静态检查确认源码里不含任何网络调用（`requests`/`urllib`/`socket` 等），但没有物理拔网线跑一次作为动态验证。
- **系统回收站只实现了 macOS**（M2）：没有用 `send2trash` 这类跨平台库（本机开发环境的权限策略会拦截 `pip install`，见下方「新增依赖」），直接把文件挪进 `~/.Trash`。这意味着：①不会写 Finder 的"原始位置"元数据，Finder 右键菜单的"放回原处"在这些文件上不可用，只能去 Finder 的废纸篓里手动拖出来（本工具自己的 `--mode revert` 还原的是「待复查」里的文件，不是回收站里的）；②外接硬盘/网络盘上的文件，macOS 原生会挪到那个卷自己的 `.Trashes` 目录，这里简化为统一挪到当前用户的 `~/.Trash`（Aimee 的照片目录在本机磁盘上，不受影响）；③Windows/Linux 没有实现，会直接报错，不会假装支持（不是 Aimee 的使用场景）。
- **「待复查」默认目录名固定为 `<输入目录名>-待复查`**：如果同一个父目录下先后清理过两个"同名"的输入目录（比如把旧批次挪开后又用回原名字），第二次的「待复查」会和第一次混在一起；正常按年份/日期命名不同目录的使用方式不会碰到这个问题。
