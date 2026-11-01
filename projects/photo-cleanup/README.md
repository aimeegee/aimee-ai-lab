# 照片清理工具（M1 预览版）

本地运行的照片清理脚本。输入一个照片目录（含子目录），识别：

- 完全重复（字节哈希）
- 相似图片聚类（感知哈希），覆盖「原图 + 编辑/裁剪版」「原照片 + 该照片的截屏」两种配对场景
- 误拍短视频（时长阈值，默认 3 秒）
- 截图（分辨率匹配已知 iPhone 屏幕 + 无相机 EXIF）
- Live Photo 的 `.MOV` 伴生文件（不会被误判成短视频）

全部判断只用本地算法（字节哈希 / 感知哈希 / 视频元数据 / EXIF），**不联网、不调用任何 LLM 或视觉模型**。

当前只实现 **M1 预览版**：只读扫描 + 生成报告，不删除、不移动任何文件。执行模式（删除完全重复副本、把可疑项移到「待复查」、支持还原）是 M2，还没做。

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
| `--report-dir` | 输入目录同级的 `photo-cleanup-reports/` | 报告输出目录 |
| `--review-dir` | — | 「待复查」文件夹路径（M2 执行模式用，M1 不生效，先占位） |
| `--mode` | `preview` | `preview`（已实现）/ `execute`（M2，传了会直接报错退出，不会假装执行） |
| `--json-only` | 关 | 只写 JSON 报告，不写 Markdown |
| `--quiet` | 关 | 不在终端打印摘要 |

示例：换一批照片、调松相似判定、短视频阈值改成 2 秒：

```bash
photo-cleanup --dir ~/Documents/Photos/2026 --similarity-threshold 16 --video-threshold-seconds 2
```

## 报告里有什么

每个被命中的文件一行：原路径、类别（完全重复/相似/短视频/截图）、命中原因（相似组带感知哈希距离，短视频带时长秒数）、动作、所属组号；每个完全重复组/相似组标出保留哪个文件；末尾有分类数量汇总，汇总数与明细行数必然一致（报告结构上保证，不是另算的）。

JSON 报告里每条命中还带着「数值证据」（`phash_distance` / `duration_seconds` 等），是为以后做反馈调参（M4，待 Aimee 用过真实数据后再设计）预留的，现在就记，成本很低。

## 判定规则要点（细节见 `../requirements.md` 和 `../decisions.md`）

- **保留优先级冲突仲裁**：完全重复 > 相似 > 短视频 > 截图标记——每个文件最终只会出现在一个类别里。
- **完全重复保留规则**：文件名不带 `(1)` / `-1` 这类副本后缀的优先保留；都带或都不带时取文件名排序第一个。
- **相似组保留规则**：① 组内有文件名配对的编辑/裁剪版（如 `IMG_1234`/`IMG_E1234`）→ 留编辑版；② 否则组内有非截图版本 → 留非截图版本；③ 否则留像素数最多的一张，像素相同留文件更大的。
- **相似判定的两种配对场景**：
  - (a) 原图 + 编辑/裁剪版：靠文件名规则识别（`IMG_xxxx` ↔ `IMG_Exxxx`），不依赖感知哈希距离，所以即使裁剪幅度较大也能配对上。
  - (b) 原照片 + 对它的截屏：靠感知哈希识别。截屏比对时会额外算一份「去掉四周近纯色边条（状态栏/黑边/手势条）」之后的感知哈希，两张图各自的「完整画面」和「去边条画面」两两比较取最小距离——这是让截屏能跟原图匹配上的关键，否则截屏四周的系统 UI 会把距离拉得很大。这个启发式规则是用合成样本调出来的默认参数，真实照片上可能需要用 `--similarity-threshold` 微调（见「已知局限」）。
- **Live Photo**：同目录、同文件名（不含扩展名）的图片 + `.MOV` 视为一体，`.MOV` 不参与短视频判断；图片命中某规则时，报告里 `.MOV` 伴生文件会显示同样的分类/动作，方便以后 M2 执行时一起处理。

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
  cli.py              命令行入口
```

分层是故意的：`walker.py`（收集事实）和 `classify.py`（做判断）都不执行任何文件系统写操作，`models.py` 里的 `Action` 枚举已经定义了「删除/移至待复查/仅标记」等动作、`FileRecord`/`DuplicateGroup` 已经记录了「谁该留、谁该走、走到哪」。M2 要做的只是加一个「执行器」模块，读这些结构真正去移动/删除文件（走系统回收站）并写操作记录，不需要改分类逻辑；M3 的 agent 调用接口可以直接读 JSON 报告，也不需要改这里的结构。

## 自测

跑验收测试（会在临时目录里生成一套合成样本集，逐条核对 requirements.md 的 AC-1 ~ AC-12）：

```bash
cd projects/photo-cleanup
python3 -m pytest tests/test_acceptance.py -v
```

也可以单独生成样本集看一眼（不跑测试）：

```bash
python3 tests/sample_generator.py /tmp/photo-cleanup-samples
```

详细的自测结果和已知局限见 lead 的回报 / `STATUS.md`。

## 已知局限

- **截图-原照片的感知哈希匹配是启发式规则，在真实照片上没有验证过**：默认参数是用代码合成的样本调出来的（见 `tests/sample_generator.py` 里 `make_screenshot_of` 的生成方式），真实场景里截屏的构图比例、App 的 UI 样式千变万化，命中率和误判率需要拿真实数据跑过才知道；这正是 `decisions.md` D-010 里说的「先跑 M1~M3 积累数据，再设计 M4 反馈调参」的原因。
- **文件名配对规则只认 `前缀_数字` / `前缀_E数字` 这一种 iOS 命名格式**，以及 `(N)`/`-N` 这两种副本后缀写法；如果 Aimee 的照片目录里有别的命名习惯（比如 Android 截图名、其他备份工具加的后缀），这部分规则可能需要再调整。
- **Live Photo 配对**：如果同一目录里同名（不含扩展名）同时存在多种图片格式（比如 `IMG_1234.HEIC` 和 `IMG_1234.JPG` 都在），当前实现会把同名的 `.MOV` 和两张图片都关联上，而不是只认一张；这种情况在真实 iPhone 导出目录里理论上不常见，但没有专门测试过。
- **AC-12（5000 文件 30 分钟内跑完 preview）没有在 5000 个真实文件上实测**：用 600 张代码合成的 1600×1200 JPEG 测过，扫描 + 分类共 9.1 秒，折算到 5000 张约 1.3 分钟，有约 20 倍余量；但真实 HEIC 照片（iPhone 拍摄通常是 3000万像素级、体积更大）解码和视频读取的耗时会比合成样本更高，没有在 Aimee 的真机环境上跑过 5000 个真实文件验证。
- **本工具本身没有做过"断网"的实测**：已经用静态检查确认源码里不含任何网络调用（`requests`/`urllib`/`socket` 等），但没有物理拔网线跑一次作为动态验证。
