"""总图图层语义映射引擎。

把 CAD 里 'DL-SS-01' 这类图层名，映射成 '给排水管道' 这类有意义的
GIS 要素类。匹配顺序：exact -> prefix -> regex，命中即返回，否则用 default。
"""

import os
import re
import shutil

import yaml


def default_mapping_path():
    return os.path.join(os.path.dirname(__file__), "presets", "tuzhi_layers.yaml")


# 内置预设名 -> presets 目录下的文件名。--layer-map 传预设名时直接加载。
_LAYER_MAP_PRESETS = {
    "tuzhi": "tuzhi_layers.yaml",
    "cass": "cass_topo_layers.yaml",
    "cass_topo": "cass_topo_layers.yaml",
}


def layer_map_presets():
    return sorted(_LAYER_MAP_PRESETS)


def _resolve_preset(name):
    if not name:
        return None
    base = name
    if base.endswith(".yaml") or base.endswith(".yml"):
        base = base[:-5] if base.endswith(".yaml") else base[:-4]
    if base in _LAYER_MAP_PRESETS:
        return os.path.join(os.path.dirname(__file__), "presets", _LAYER_MAP_PRESETS[base])
    return None


def load_mapping(path=None):
    if path is None:
        return yaml.safe_load(open(default_mapping_path(), encoding="utf-8"))
    # 1) 预设名（如 cass / tuzhi）  2) 真实文件路径
    preset = _resolve_preset(path)
    if preset:
        path = preset
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def classify(mapping, layer: str) -> dict:
    rules = mapping.get("rules", [])
    for r in rules:
        m = r.get("match", "")
        t = r.get("type", "exact")
        if t == "exact" and layer == m:
            return r
        if t == "prefix" and layer.startswith(m):
            return r
        if t == "regex" and re.search(m, layer, re.IGNORECASE):
            return r
    return mapping.get(
        "default", {"feature_class": "unknown", "category": "other", "label": "未分类"}
    )


def write_template(output_path: str, preset: str = "tuzhi"):
    """导出内置模板到用户目录，方便按需增删规则。

    preset 可选 'tuzhi'（工厂总图）或 'cass'（南方 CASS 地形图）。
    直接复制 presets/<name>.yaml，避免模板在代码里出现第二份而产生漂移。
    """
    src = _resolve_preset(preset) or default_mapping_path()
    if os.path.abspath(src) != os.path.abspath(output_path):
        shutil.copyfile(src, output_path)
