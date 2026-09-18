import ezdxf
import json
import os
import tempfile

from pyproj import CRS, Transformer

from plotsmith import coords, convert, layermap


def test_coords_gauss():
    # 3 度带：中央子午线 117E 对应 CM 版 EPSG:4548（"CGCS2000 / 3-degree Gauss-Kruger CM 117E"）
    # 注：同为 CM117E 的带号版 EPSG:4527 在部分 proj 构建下反算返回 inf，故展示统一用 CM 版。
    assert coords.gauss_epsg(117, 3) == 4548
    # 6 度带无 CM 版 EPSG，仍用带号版：CM117E -> zone 20 -> EPSG:4498
    assert coords.gauss_epsg(117, 6) == 4498
    # 关键：生成的 EPSG 必须能被 pyproj 真正解析（防止预设号写错）
    name3 = CRS.from_epsg(coords.gauss_epsg(117, 3)).name
    assert name3.startswith("CGCS2000") and "117E" in name3
    assert CRS.from_epsg(coords.gauss_epsg(117, 6)).name.startswith("CGCS2000")
    assert coords.resolve_epsg("cgcs2000") == 4490
    assert coords.resolve_epsg("epsg:4326") == 4326
    # 命名预设与 gauss_epsg 必须一致
    assert coords.resolve_epsg("cgcs2000-3-117") == coords.gauss_epsg(117, 3)
    assert coords.resolve_epsg("cgcs2000-6-117") == coords.gauss_epsg(117, 6)


def test_gk_inverse_transform():
    """回归测试：高斯-克吕格必须能反算出有限经纬度（曾发生 proj 返回 inf）。"""
    for spec, expect_lon in [("cgcs2000-3-117", 117.0), ("cgcs2000-6-117", 117.0)]:
        crs = coords.crs_from_spec(spec)
        t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        lon, lat = t.transform(500000, 4000000)
        assert abs(lon) < 180 and abs(lat) < 90, f"{spec} 反算非有限值: {lon},{lat}"
        # 东移 500km 处即中央子午线附近（x_0=500000）
        assert abs(lon - expect_lon) < 1.0, f"{spec} 反算经度 {lon} 偏离 {expect_lon}"
    # 北京54 / 西安80 也应可用
    for spec in ("beijing54-3-117", "xian80-3-117"):
        crs = coords.crs_from_spec(spec)
        t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        lon, lat = t.transform(500000, 4000000)
        assert abs(lon - 117.0) < 1.0, f"{spec} 反算经度异常: {lon}"


def _make_sample_dxf(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    line = msp.add_line((0, 0), (10, 0))
    line.dxf.layer = "DL-SS-01"
    poly = msp.add_lwpolyline([(0, 0), (0, 10), (10, 10), (0, 0)])
    poly.dxf.layer = "JZ-01"
    doc.saveas(path)


def test_convert_dxf_to_geojson():
    d = tempfile.mkdtemp()
    dxf = os.path.join(d, "t.dxf")
    _make_sample_dxf(dxf)
    out = os.path.join(d, "out.geojson")
    n = convert.convert(dxf, out, "wgs84", "wgs84", None, "geojson")
    assert n == 2
    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["features"]) == 2
    fcs = {f["properties"]["feature_class"] for f in data["features"]}
    assert "water_supply_pipe" in fcs
    assert "building" in fcs


# 覆盖总图各专业图层 -> 期望的语义要素类（防止改模板时悄悄退化）
EXPECTED_LAYERS = {
    "DL-SS-01": "water_supply_pipe",
    "JZ-01": "building",
    "SB-01": "equipment",
    "WQ-01": "fence",
    "TL-01": "railway",
    "XF-01": "fire_pipe",
    "LH-01": "green_belt",
}


def test_layer_semantics_on_sample_plant():
    """用 examples/ 里的模拟总图验证：所有图层都应被识别，不能落到 unknown。"""
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, os.pardir, "examples"))
    import make_sample_dxf as sample

    d = tempfile.mkdtemp()
    dxf = sample.build(os.path.join(d, "plant.dxf"))

    out = os.path.join(d, "out.geojson")
    n = convert.convert(dxf, out, "cgcs2000-3-117", "wgs84", None, "geojson")
    assert n == len(EXPECTED_LAYERS)

    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    got = {f["properties"]["layer"]: f["properties"]["feature_class"] for f in data["features"]}
    assert got == EXPECTED_LAYERS, f"图层语义映射退化: {got}"
    assert "unknown" not in got.values()
    # 中文字段应随图层一起带出
    labels = {f["properties"]["label"] for f in data["features"]}
    assert "给水管道" in labels
    # GeoJSON 按 RFC 7946 固定输出 WGS84，且经度落在 117E 附近
    assert data["crs"]["properties"]["name"] == "EPSG:4326"
    lon = data["features"][0]["geometry"]["coordinates"][0][0]
    assert abs(lon - 117.0) < 1.0, f"经度异常: {lon}"


def test_shp_writes_prj():
    """SHP 必须带 .prj，否则 ArcMap/QGIS 打开会报未知坐标系。"""
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, os.pardir, "examples"))
    import make_sample_dxf as sample

    d = tempfile.mkdtemp()
    dxf = sample.build(os.path.join(d, "plant.dxf"))
    out_dir = os.path.join(d, "shpout")
    convert.convert(dxf, out_dir, "cgcs2000-3-117", "cgcs2000-3-117", None, "shp")
    prj = os.path.join(out_dir, "polygons.prj")
    assert os.path.exists(prj)
    body = open(prj, encoding="utf-8").read()
    # ESRI WKT 把横轴墨卡托写成 Gauss_Kruger，标准 WKT 写成 Transverse_Mercator
    assert ("Gauss_Kruger" in body) or ("Transverse_Mercator" in body), body[:120]
    # 名称必须是正规 CGCS2000，而不是 unknown（PROJ 字符串兜底时才会是 unknown）
    assert "CGCS2000" in body, f".prj 缺少坐标系名称: {body[:80]}"


def test_polyline_entity_extraction():
    """回归：POLYLINE（2D 多段线，等高线常见）必须能被提取，不能静默丢失。

    ezdxf 1.4.x 中 e.vertices 是属性不是方法，曾因调用 e.vertices() 报错而整类丢失。
    """
    d = tempfile.mkdtemp()
    dxf = os.path.join(d, "pl.dxf")
    doc = ezdxf.new()
    msp = doc.modelspace()
    pl = msp.add_polyline2d([(0, 0), (10, 0), (10, 10), (0, 0)])
    pl.dxf.layer = "DGX"
    doc.saveas(dxf)

    out = os.path.join(d, "o.geojson")
    n = convert.convert(dxf, out, "wgs84", "wgs84", "cass", "geojson")
    assert n == 1
    data = json.load(open(out, encoding="utf-8"))
    assert data["features"][0]["properties"]["feature_class"] == "contour_line"


def test_cass_layer_mapping_preset():
    """CASS 地形图预设：所有标准图层码应命中，且不能子串误判。"""
    mp = layermap.load_mapping("cass")  # 预设名直接解析
    expected = {
        "JMD": "building",
        "DLSS": "road",
        "DLDW": "landmark",
        "GXYZ": "pipeline",
        "SXSS": "water",
        "ZBTZ": "vegetation",
        "TK": "map_frame",
        "ASSIST": "annotation",
        "GCD": "elevation_point",
        "DGX": "contour_line",
        "DMTZ": "landform",
    }
    for layer, fc in expected.items():
        got = layermap.classify(mp, layer)["feature_class"]
        assert got == fc, f"{layer} -> {got}（期望 {fc}）"
    # 子串误判回归：DLDW 曾误判绿化带、ZBTZ 曾误判注记
    assert layermap.classify(mp, "DLDW")["feature_class"] != "green_belt"
    assert layermap.classify(mp, "ZBTZ")["feature_class"] != "annotation"
