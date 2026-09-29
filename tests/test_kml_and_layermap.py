"""KML 输出结构 + 自定义图层映射 YAML 往返的回归测试。"""

import ezdxf
import os
import tempfile
import xml.etree.ElementTree as ET

import yaml

from plotsmith import convert, layermap


def _make_dxf(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    line = msp.add_line((0, 0), (10, 0))
    line.dxf.layer = "DL-SS-01"
    poly = msp.add_lwpolyline([(0, 0), (0, 10), (10, 10), (0, 0)])
    poly.dxf.layer = "JZ-01"
    doc.saveas(path)


def test_kml_output_is_valid_and_grouped():
    """DXF -> KML：文件必须有效、含 Placemark、坐标不为空、按要素类分组。"""
    d = tempfile.mkdtemp()
    dxf = os.path.join(d, "t.dxf")
    _make_dxf(dxf)
    out = os.path.join(d, "out.kml")
    n = convert.convert(dxf, out, "wgs84", "wgs84", None, "kml")
    assert n == 2
    assert os.path.exists(out)

    root = ET.parse(out).getroot()
    assert "kml" in root.tag.lower(), "根元素不是 kml"

    placemarks = [el for el in root.iter() if el.tag.endswith("Placemark")]
    assert len(placemarks) == 2, f"Placemark 数量异常: {len(placemarks)}"

    coords = [el for el in root.iter() if el.tag.endswith("coordinates")]
    assert coords, "未写出任何 <coordinates>"
    assert all(c.text and c.text.strip() for c in coords), "存在空坐标"

    # KML 不嵌 CRS（规范只允许 WGS84），但内容里应能看到中文标签（图层语义已生效）
    names = [el.text for el in root.iter() if el.tag.endswith("name")]
    assert "给水管道" in names, "KML 未带出图层中文标签"


def test_custom_layermap_yaml_roundtrip():
    """自定义图层 YAML 必须能被 load_mapping 读取、classify 命中且不串规则。"""
    d = tempfile.mkdtemp()
    yml = os.path.join(d, "mymap.yaml")
    spec = {
        "rules": [
            {"match": "MY-", "type": "prefix", "feature_class": "my_pipe", "category": "pipe", "label": "我的管线"},
            {"match": "SPEC-01", "type": "exact", "feature_class": "special", "category": "misc", "label": "专用"},
        ],
        "default": {"feature_class": "unknown", "category": "other", "label": "未分类"},
    }
    with open(yml, "w", encoding="utf-8") as f:
        yaml.safe_dump(spec, f, allow_unicode=True)

    mp = layermap.load_mapping(yml)  # 走文件路径分支
    assert layermap.classify(mp, "MY-A")["feature_class"] == "my_pipe"
    assert layermap.classify(mp, "SPEC-01")["feature_class"] == "special"
    # 未匹配应落到 default
    assert layermap.classify(mp, "OTHER")["feature_class"] == "unknown"
    # 文件分支不应误命中内置预设（预设名解析）
    assert layermap.classify(mp, "cass-JMD")["feature_class"] == "unknown"
