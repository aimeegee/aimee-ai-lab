"""字节哈希（完全重复）与感知哈希（相似聚类）。

性能说明（对应 AC-12，5000 文件 30 分钟内跑完 preview）：
感知哈希两两比较若用纯 Python 双重循环，5000 张图会有约 1250 万对比较，
容易超时。这里把每张图的哈希打包成位数组，用 numpy 分块做向量化的
异或 + popcount，再用并查集把距离 <= 阈值的两两关系合并成组。
"""

from __future__ import annotations

import hashlib

import imagehash
import numpy as np
from PIL import Image

CHUNK_SIZE = 1024 * 1024


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def autotrim_borders(
    img: "Image.Image",
    extreme_thresh: float = 40.0,
    var_thresh: float = 10.0,
    max_trim_frac: float = 0.45,
) -> "Image.Image":
    """去掉四周「近乎纯色、且颜色偏极端（很黑或很白/很亮）」的边条。

    用途：截图四周常见的状态栏（接近纯白/浅灰）、黑边letterbox、
    底部手势条（接近纯黑），这些边条会严重干扰感知哈希与原图的比对；
    真实照片内容偶尔也会有大片低方差区域（比如晴空），但很少同时满足
    "颜色极端 + 低方差 + 贴着图片边缘连续一长条"，所以用
    "极端亮度 + 低方差" 的组合条件尽量只剪掉系统 UI 边条，不误剪照片本身。
    这是一个启发式规则，默认只在相似度比对时作为辅助视角使用（见 cluster_similar），
    不改变任何文件本身。
    """
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w, _ = arr.shape

    def row_is_bar(y: int) -> bool:
        row = arr[y]
        mean = row.mean()
        var = row.std(axis=0).mean()
        return var < var_thresh and (mean < extreme_thresh or mean > 255 - extreme_thresh)

    def col_is_bar(x: int) -> bool:
        col = arr[:, x]
        mean = col.mean()
        var = col.std(axis=0).mean()
        return var < var_thresh and (mean < extreme_thresh or mean > 255 - extreme_thresh)

    top = 0
    while top < h * max_trim_frac and row_is_bar(top):
        top += 1
    bottom = h - 1
    while bottom > h * (1 - max_trim_frac) and bottom > top and row_is_bar(bottom):
        bottom -= 1
    left = 0
    while left < w * max_trim_frac and col_is_bar(left):
        left += 1
    right = w - 1
    while right > w * (1 - max_trim_frac) and right > left and col_is_bar(right):
        right -= 1

    if bottom <= top or right <= left:
        return img
    return img.crop((left, top, right + 1, bottom + 1))


def compute_phash_variants(img: "Image.Image", hash_size: int = 16) -> tuple["imagehash.ImageHash", "imagehash.ImageHash"]:
    """返回 (完整画面 phash, 去边条后画面 phash)。"""
    full = imagehash.phash(img, hash_size=hash_size)
    trimmed_img = autotrim_borders(img)
    trimmed = imagehash.phash(trimmed_img, hash_size=hash_size)
    return full, trimmed


def _hash_to_bits(h: "imagehash.ImageHash") -> np.ndarray:
    return h.hash.flatten().astype(np.uint8)


def _pack(bits_matrix: np.ndarray) -> np.ndarray:
    """把 (n, n_bits) 的 0/1 矩阵打包成 (n, n_bytes) 的 uint8，方便做向量化异或。"""
    return np.packbits(bits_matrix, axis=1)


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def groups(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for i in range(len(self.parent)):
            r = self.find(i)
            out.setdefault(r, []).append(i)
        return out


def phash_distance(
    a: tuple["imagehash.ImageHash", "imagehash.ImageHash"],
    b: tuple["imagehash.ImageHash", "imagehash.ImageHash"],
) -> int:
    """两张图的「最终距离」= 4 种组合（full-full / full-trim / trim-full / trim-trim）里的最小值。

    取最小值是为了让「截图 vs 原照片主体内容」这种只有裁掉边条后才能对齐的情况
    也能被识别到（见 requirements.md「截图前/截图」场景 b）；已用合成样本验证
    （tests/sample_generator.py + tests/test_acceptance.py）这不会提高誤判率。
    """
    a_full, a_trim = a
    b_full, b_trim = b
    return min(a_full - b_full, a_full - b_trim, a_trim - b_full, a_trim - b_trim)


def cluster_similar(
    hash_variants: list[tuple["imagehash.ImageHash", "imagehash.ImageHash"]],
    threshold: int,
    row_chunk: int = 200,
) -> list[list[int]]:
    """对一批 (phash_full, phash_trimmed) 做相似聚类，返回每组的文件下标列表（组大小 >= 2）。

    用 numpy 分块向量化算全量两两距离（而不是 Python 双重循环逐对调用 phash_distance），
    是为了在几千张图片规模下仍能在合理时间内跑完（对应 AC-12）。
    """
    n = len(hash_variants)
    if n == 0:
        return []

    full_bits = np.stack([_hash_to_bits(h[0]) for h in hash_variants])
    trim_bits = np.stack([_hash_to_bits(h[1]) for h in hash_variants])
    full_packed = _pack(full_bits)
    trim_packed = _pack(trim_bits)

    uf = UnionFind(n)

    for start in range(0, n, row_chunk):
        end = min(start + row_chunk, n)
        rows_full = full_packed[start:end]
        rows_trim = trim_packed[start:end]

        # 4 种组合各自算一遍，取逐元素最小值
        best = None
        for rows in (rows_full, rows_trim):
            for cols in (full_packed, trim_packed):
                xor = rows[:, None, :] ^ cols[None, :, :]
                dist = np.bitwise_count(xor).sum(axis=2)
                best = dist if best is None else np.minimum(best, dist)

        for local_i in range(end - start):
            i = start + local_i
            row = best[local_i]
            # 只看 j > i，避免重复和自比较
            js = np.nonzero(row[i + 1 :] <= threshold)[0] + (i + 1)
            for j in js:
                uf.union(i, int(j))

    groups_raw = uf.groups()
    groups = [sorted(members) for members in groups_raw.values() if len(members) >= 2]
    groups.sort(key=lambda g: g[0])
    return groups
