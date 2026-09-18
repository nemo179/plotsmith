"""转换管线：DXF 读取 -> 几何提取 -> 图层语义映射 -> 坐标系变换 -> 写出。

支持输出：KML（单文件）、GeoJSON（单文件）、SHP（按几何类型分文件目录）。
DWG 需先经 LibreDWG dwg2dxf 转 DXF（见 CLI 提示）。
"""

import json
import os

import ezdxf
import shapely.geometry as sg
from pyproj import CRS, Transformer

from . import coords, layermap

GEOM_POINT = "point"
GEOM_LINE = "line"
GEOM_POLYGON = "polygon"


def _entity_points(e):
    """返回实体定义点列表 [(x,y), ...]，不支持返回 None。

    注意：ezdxf 1.4.x 的 DXFVertex/Vec3 对切片 `[:2]` 行为不稳定，
    统一改用 .x/.y 属性访问，跨版本更稳健。
    """
    try:
        dxftype = e.dxftype()
        if dxftype == "LINE":
            return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        if dxftype == "LWPOLYLINE":
            # get_points("xy") 返回的是 (float, float) 元组，不是 Vec 对象
            return [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
        if dxftype == "POLYLINE":
            # ezdxf 1.4.x: e.vertices 是属性（list），不是方法
            return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if dxftype == "POINT":
            return [(e.dxf.location.x, e.dxf.location.y)]
        if dxftype in ("CIRCLE", "ARC"):
            return [(e.dxf.center.x, e.dxf.center.y)]
        if dxftype == "TEXT":
            return [(e.dxf.insert.x, e.dxf.insert.y)]
        if dxftype == "INSERT":
            return [(e.dxf.insert.x, e.dxf.insert.y)]
    except Exception:
        return None
    return None


def _is_closed(pts):
    return pts[0] == pts[-1]


def _to_geometry(pts, dxftype, closed=False):
    if not pts:
        return None, None
    if dxftype in ("POINT", "CIRCLE", "ARC", "TEXT", "INSERT"):
        return sg.Point(pts[0]), GEOM_POINT
    if dxftype == "LINE":
        return sg.LineString(pts), GEOM_LINE
    # polyline 类
    if len(pts) == 1:
        return sg.Point(pts[0]), GEOM_POINT
    if len(pts) == 2:
        return sg.LineString(pts), GEOM_LINE
    if closed or _is_closed(pts):
        return sg.Polygon(pts), GEOM_POLYGON
    return sg.LineString(pts), GEOM_LINE


def _transform_geom(g, transformer):
    if g.is_empty:
        return g
    if isinstance(g, sg.Point):
        x, y = transformer.transform(g.x, g.y)
        return sg.Point(x, y)
    if isinstance(g, sg.LineString):
        return sg.LineString([transformer.transform(x, y) for x, y in g.coords])
    if isinstance(g, sg.Polygon):
        ext = [transformer.transform(x, y) for x, y in g.exterior.coords]
        ints = [
            [transformer.transform(x, y) for x, y in ring.coords]
            for ring in g.interiors
        ]
        return sg.Polygon(ext, ints)
    return g


def _ext(path):
    return os.path.splitext(path)[1].lstrip(".").lower()


def list_layers(input_path):
    doc = ezdxf.readfile(input_path)
    return sorted({e.dxf.layer for e in doc.modelspace()})


def convert(input_path, output_path, src_cs, dst_cs, layer_map_path=None, fmt=None):
    """执行一次转换，返回写出要素数量。"""
    fmt = fmt or _ext(output_path)
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()
    mapping = layermap.load_mapping(layer_map_path)

    src_crs = coords.crs_from_spec(src_cs)
    # KML / GeoJSON 都是给 Web 与 Google Earth 用的：
    # KML 规范只允许 WGS84；GeoJSON(RFC 7946) 默认 CRS 也是 WGS84，否则下游几乎必踩坑。
    # 想保留高斯投影请用 SHP 输出。
    if fmt in ("kml", "geojson"):
        target_crs = CRS.from_epsg(4326)
    else:
        target_crs = coords.crs_from_spec(dst_cs)
    transformer = Transformer.from_crs(src_crs, target_crs, always_xy=True)
    epsg_int = target_crs.to_epsg()
    crs_name = f"EPSG:{epsg_int}" if epsg_int else str(target_crs.to_wkt())

    features = []
    for e in msp:
        pts = _entity_points(e)
        if pts is None:
            continue
        closed = False
        if e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            try:
                closed = bool(e.dxf.flags & 1)
            except Exception:
                closed = False
        g, gtype = _to_geometry(pts, e.dxftype(), closed)
        if g is None:
            continue
        g = _transform_geom(g, transformer)
        fm = layermap.classify(mapping, e.dxf.layer)
        props = {
            "layer": e.dxf.layer,
            "feature_class": fm["feature_class"],
            "category": fm["category"],
            "label": fm.get("label", ""),
        }
        features.append((gtype, g, props))

    if fmt == "kml":
        _write_kml(features, output_path)
    elif fmt == "geojson":
        _write_geojson(features, output_path, crs_name)
    elif fmt == "shp":
        _write_shp(features, output_path, target_crs)
    else:
        raise ValueError(f"不支持的输出格式: {fmt}")
    return len(features)


# ----------------------------- 写出实现 -----------------------------


def _write_geojson(features, path, crs_name):
    """crs_name 形如 'EPSG:4527' 或原始 spec（如 'cgcs2000-3-117'）。"""
    fc = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": crs_name}},
        "features": [
            {"type": "Feature", "properties": p, "geometry": sg.mapping(g)}
            for _, g, p in features
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)


def _kml_geom(g):
    if isinstance(g, sg.Point):
        return "Point", f"{g.x},{g.y},0"
    if isinstance(g, sg.LineString):
        body = " ".join(f"{x},{y},0" for x, y in g.coords)
        return "LineString", body
    if isinstance(g, sg.Polygon):
        body = " ".join(f"{x},{y},0" for x, y in g.exterior.coords)
        return (
            "Polygon",
            f"<outerBoundaryIs><LinearRing><coordinates>{body}</coordinates></LinearRing></outerBoundaryIs>",
        )
    return "Point", "0,0,0"


def _write_kml(features, path):
    from xml.sax.saxutils import escape

    folders = {}
    for gtype, g, props in features:
        folders.setdefault(props["feature_class"], []).append((g, props))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
    ]
    for fc_name, items in folders.items():
        parts.append(f"<Folder><name>{escape(fc_name)}</name>")
        for g, props in items:
            tag, body = _kml_geom(g)
            parts.append("<Placemark>")
            parts.append(f"<name>{escape(props.get('label') or fc_name)}</name>")
            parts.append(
                f"<description>layer={escape(props['layer'])}; category={escape(props['category'])}</description>"
            )
            parts.append(f"<{tag}>{body}</{tag}>")
            parts.append("</Placemark>")
        parts.append("</Folder>")
    parts.append("</Document></kml>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def _write_shp(features, path, target_crs=None):
    """按几何类型分文件写出 SHP，并附带 .prj（否则 ArcMap/QGIS 打开会提示未知坐标系）。"""
    import shapefile

    os.makedirs(path, exist_ok=True)
    by_type = {"point": [], "line": [], "polygon": []}
    for gtype, g, props in features:
        by_type[gtype].append((g, props))

    for gtype, items in by_type.items():
        if not items:
            continue
        shp_path = os.path.join(path, gtype + "s.shp")
        w = shapefile.Writer(shp_path)
        # DBF 字段名最多 10 字节，用短名避免被截断成 feature_cl
        w.field("layer", "C", 80)
        w.field("fclass", "C", 40)
        w.field("category", "C", 20)
        w.field("label", "C", 40)
        for g, props in items:
            w.record(
                props["layer"], props["feature_class"], props["category"], props.get("label", "")
            )
            if gtype == "point":
                w.point(g.x, g.y)
            elif gtype == "line":
                w.line([list(g.coords)])
            elif gtype == "polygon":
                w.poly([list(g.exterior.coords)])
        w.close()

        if target_crs is not None:
            prj_path = os.path.splitext(shp_path)[0] + ".prj"
            with open(prj_path, "w", encoding="utf-8") as f:
                f.write(_esri_wkt(target_crs))


def _esri_wkt(crs) -> str:
    """优先输出 ESRI WKT（ArcMap 认）；pyproj 不支持则退回标准 WKT。"""
    for fn, arg in ((crs.to_wkt, "WKT1_ESRI"), (crs.to_wkt, None)):
        try:
            return fn(arg) if arg else fn()
        except Exception:
            continue
    return str(crs)
