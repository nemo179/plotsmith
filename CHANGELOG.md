# Changelog

本文件按 [Keep a Changelog](https://keepachangelog.com/) 约定记录版本变更。

## [0.1.0] — 2026-09-28

首个可用版本（MVP）。聚焦「工厂总图 / CAD 智能格式互转」，零 GDAL 依赖的纯 Python 实现。

### 新增

- **转换管线**：DXF → KML / GeoJSON / SHP（SHP 按几何类型分文件并自动写 `.prj`）。
- **中文坐标系一键处理**：CGCS2000 / 北京54 / 西安80 / 高斯-克吕格分带，支持
  `cgcs2000-3-117`、`epsg:4548` 等写法，无需手查 EPSG。
- **总图图层语义映射**：`DL-SS-01` 这类 CAD 图层名自动识别为「给水管道」等
  GIS 要素类 + 中文标签；内置 25 条总图专业规则。
- **南方 CASS 地形图预设**（`cass`）：覆盖 JMD / DLSS / DLSS / GXYZ / SXSS / ZBTZ /
  GCD / DGX / DMTZ 等标准图层码。
- **KML / GeoJSON 固定输出 WGS84**（Google Earth / Web 直接可开）；SHP 保留高斯投影。
- **CLI**（`plotsmith convert` / `coords` / `map-layers`）。
- **高斯-克吕格两道坑的稳健处理**：带号版 EPSG 反算自检 + PROJ 字符串兜底，避免静默产出 `inf` 坐标。
- **单元测试**：坐标系、反算、图层语义、SHP 写 `.prj`、多段线提取、CASS 预设等回归测试。
- **CI**：GitHub Actions 在 Python 3.9 / 3.11 / 3.13 上跑 `pytest`。

### 已知限制

- DWG 不可直读（AutoCAD 私有格式），需 `dwg2dxf` 预转一步 DXF。
- CIRCLE / ARC 当前取圆心转点，未做圆弧离散化。
- 不解析块属性与扩展数据（XData）。
- `validate` 命令暂为占位。

[0.1.0]: https://github.com/nemo179/plotsmith/releases/tag/v0.1.0
