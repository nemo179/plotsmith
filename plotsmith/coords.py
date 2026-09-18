"""坐标系预设与 EPSG 解析。

内置常用中文坐标系预设，并提供高斯-克吕格（Gauss-Krüger, GK）带 CRS 构造。

GK 采取「标准 EPSG 优先 + 反算自检 + PROJ 字符串兜底」：
部分 proj 构建对"带号版" GK EPSG（如 4527/4498）反算返回 inf，
因此先试标准 EPSG 并做一次反算体检，不通过再用 PROJ 字符串
（+proj=tmerc）构造，保证跨 proj 版本都能算对。
"""

import re

from pyproj import CRS

# 地理坐标系（直接用 EPSG，pyproj 反算正常）
GEO_PRESETS = {
    "wgs84": 4326,
    "cgcs2000": 4490,
    "beijing54": 4214,
    "xian80": 4610,
}

# 椭球：CGCS2000 与 GRS80 在实用精度内一致；北京54=Krassovsky；西安80=IAU76 参数
# 用 "key=val,key=val" 形式，便于拼成 "+a=... +rf=..." PROJ 片段。
_ELLPS = {
    "cgcs2000": "GRS80",
    "beijing54": "krass",
    "xian80": "a=6378140,rf=298.257",
}

_GK_RE = re.compile(
    r"^(?P<datum>cgcs2000|beijing54|xian80)-(?P<band>[36])-(?P<cm>\d+(?:\.\d+)?)$"
)


def _ellps_token(datum: str) -> str:
    e = _ELLPS.get(datum, "GRS80")
    if "=" in e:
        return "+" + e.replace(",", " +")  # a=6378140,rf=298.257 -> +a=... +rf=...
    return f"+ellps={e}"


def _gk_crs(datum: str, band: int, cm: float) -> CRS:
    """用 PROJ 字符串构造高斯-克吕格 CRS（横轴墨卡托）。band 仅影响 CM 取值来源。"""
    token = _ellps_token(datum)
    proj = (
        f"+proj=tmerc +lat_0=0 +lon_0={cm} +k_0=1 "
        f"+x_0=500000 +y_0=0 {token} +units=m +no_defs +type=crs"
    )
    return CRS.from_proj4(proj)


# 反算自检缓存：EPSG -> bool（能否正确反算出有限经纬度）
_INVERTIBLE_CACHE = {}

# 自检样本点：中国陆域内的高斯投影坐标（东移 500km 处即中央子午线）
_PROBE_XY = (500000.0, 4000000.0)


def _epsg_invertible(epsg: int) -> bool:
    """检查该 EPSG 能否反算出合理经纬度。

    部分 proj 构建对"带号版"高斯-克吕格 EPSG（如 4527/4498）反算会返回 inf。
    这里用一次真实反算来体检并缓存结果——宁可多几毫秒，
    也不能让转换结果变成 inf 悄悄污染下游数据。
    """
    if epsg in _INVERTIBLE_CACHE:
        return _INVERTIBLE_CACHE[epsg]
    ok = False
    try:
        from pyproj import Transformer

        t = Transformer.from_crs(epsg, 4326, always_xy=True)
        lon, lat = t.transform(*_PROBE_XY)
        ok = abs(lon) < 180 and abs(lat) < 90
    except Exception:
        ok = False
    _INVERTIBLE_CACHE[epsg] = ok
    return ok


def crs_from_spec(cs) -> CRS:
    """把坐标系说明转成 pyproj.CRS。

    支持：wgs84 / cgcs2000 / beijing54 / xian80 / epsg:XXXX / XXXX /
    <datum>-<band>-<cm>（如 cgcs2000-3-117）。

    高斯-克吕格采用「标准 EPSG 优先 + 反算自检 + PROJ 字符串兜底」策略：
    先试标准 EPSG（能拿到正规 CRS 名称，写出的 .prj 在 ArcMap/QGIS 里
    显示为 CGCS2000 而不是 unknown），自检不通过再用 PROJ tmerc 字符串构造，
    保证任何 proj 版本都能算对。
    """
    s = str(cs).strip().lower()
    if s.startswith("epsg:"):
        return CRS.from_epsg(int(s.split(":")[1]))
    if s.isdigit():
        return CRS.from_epsg(int(s))
    if s in GEO_PRESETS:
        return CRS.from_epsg(GEO_PRESETS[s])
    m = _GK_RE.match(s)
    if m:
        datum, band, cm = m.group("datum"), int(m.group("band")), float(m.group("cm"))
        try:
            epsg = gauss_epsg(cm, band, datum)
        except ValueError:
            epsg = None
        if epsg and _epsg_invertible(epsg):
            return CRS.from_epsg(epsg)
        return _gk_crs(datum, band, cm)
    raise ValueError(
        f"未知坐标系: {cs}。可用预设: {sorted(GEO_PRESETS)}，"
        f"或 <datum>-<band>-<cm>（如 cgcs2000-3-117），或 epsg:XXXX"
    )


def resolve_epsg(cs) -> int:
    """返回 EPSG 整数（地理/已知预设/GK 带号）。GK 带号返回其标准 EPSG 供展示。"""
    s = str(cs).strip().lower()
    if s.startswith("epsg:"):
        return int(s.split(":")[1])
    if s.isdigit():
        return int(s)
    if s in GEO_PRESETS:
        return GEO_PRESETS[s]
    m = _GK_RE.match(s)
    if m:
        return gauss_epsg(float(m.group("cm")), int(m.group("band")), m.group("datum"))
    raise ValueError(f"未知坐标系: {cs}")


def gauss_epsg(central_meridian: float, band: int = 3, datum: str = "cgcs2000") -> int:
    """返回 GK 带的"标准" EPSG 整数（用于展示/记录）。

    3 度带用 CM 版 EPSG（4534 + (cm-75)/3，本机可反算）；
    6 度带本机无 CM 版 EPSG，返回带号版（仅供展示，实际转换请用 crs_from_spec）。
    """
    if datum != "cgcs2000":
        raise ValueError("带号 EPSG 计算器目前仅支持 datum=cgcs2000")
    if band == 3:
        return 4534 + int((central_meridian - 75) / 3 + 0.5)
    if band == 6:
        return 4478 + int(central_meridian / 6 + 0.5)
    raise ValueError("band 只能为 3 或 6")


def list_presets():
    return dict(sorted(GEO_PRESETS.items()))
