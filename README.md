# plotsmith / 总图匠

![CI](https://github.com/nemo179/plotsmith/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/nemo179/plotsmith)
![Python](https://img.shields.io/badge/python-3.9%20%7C%203.11%20%7C%203.13-blue)

工厂总图规划师的**智能格式互转**工具。零 GDAL 依赖的纯 Python 实现。

**English:** A zero-GDAL Python toolkit for CAD↔GIS format conversion with first-class
Chinese coordinate systems (CGCS2000 / Gauss-Krüger) and CASS topographic layer semantics.

> MVP 范围：智能格式互转（中文坐标系一键处理 + 总图图层语义映射）。
> 后续支柱：三维总平融合（Cesium 3D Tiles）、总图规范校验（GB50187 / 防火间距）。

## 为什么不用 GDAL

通用转换引擎（GDAL/ogr2ogr、QGIS）在 Windows 上装 GDAL 绑定极坑，
而且导出的图层名对规划师毫无意义。plotsmith 用纯 Python 库
（ezdxf / shapely / pyproj / pyshp）实现，终端用户**免装 GDAL**；
同时叠加两层领域知识作为核心差异：

1. **中文坐标系一键处理** —— CGCS2000 / 北京54 / 西安80 / 高斯-克吕格分带，
   不用手动抠 EPSG，`cgcs2000-3-117` 这种写法直接就能用。
2. **总图图层语义映射** —— `DL-SS-01` 这类 CAD 图层名自动变成「给水管道」
   这类有意义的 GIS 要素类 + 中文标签，内置 25 条总图专业规则；另附
   **南方 CASS 地形图预设**（`cass`），覆盖 JMD/DLSS/GXYZ/SXSS/ZBTZ 等标准码。

## 安装

```bash
pip install -e .
# 需要 LLM 图层建议功能时：pip install -e ".[llm]"
```

核心依赖：ezdxf, shapely, pyproj, pyshp, click, pyyaml（均有 wheel，免编译）。
`requests` 仅在 `map-layers suggest` 时懒加载，未装也不影响转换。

## 使用

```bash
# 坐标系预设列表
plotsmith coords list

# 高斯-克吕格带 EPSG 计算（中央子午线 117°，3 度带）
plotsmith coords epsg --central 117 --band 3     # -> EPSG:4548（CM 版）

# DXF -> KML（自动转 WGS84，Google Earth 直接可开）
plotsmith convert input.dxf output.kml --src-cs cgcs2000-3-117

# DXF -> SHP（保留高斯投影，按几何类型分文件 + 自动写 .prj）
plotsmith convert input.dxf out_shp_dir --to shp \
    --src-cs cgcs2000-3-117 --dst-cs cgcs2000-3-117

# DXF -> GeoJSON
plotsmith convert input.dxf output.geojson --src-cs beijing54-3-117

# 导出可编辑的图层语义映射模板（按需增删自己的图层规则）
plotsmith map-layers init
plotsmith convert input.dxf out.kml --layer-map tuzhi_layers.yaml

# 地形图（南方 CASS 标准图层码）用内置 cass 预设，直接命中 JMD/DLSS/GXYZ...
plotsmith map-layers init --preset cass --output cass_layers.yaml
plotsmith convert input.dxf out.kml --layer-map cass

# DWG 是 AutoCAD 私有格式，先用 LibreDWG 转一步 DXF
dwg2dxf input.dwg -o input.dxf
```

试跑自带样例：

```bash
python examples/make_sample_dxf.py
plotsmith convert examples/plant.dxf plant.kml --src-cs cgcs2000-3-117
```

### 坐标系写法

| 写法 | 含义 |
| --- | --- |
| `wgs84` | WGS 84（EPSG:4326） |
| `cgcs2000` | 2000 国家大地坐标系（EPSG:4490） |
| `beijing54` / `xian80` | 北京 54（EPSG:4214）/ 西安 80（EPSG:4610） |
| `cgcs2000-3-117` | CGCS2000 高斯-克吕格 3 度带，中央子午线 117°E |
| `cgcs2000-6-117` | CGCS2000 高斯-克吕格 6 度带，中央子午线 117°E |
| `epsg:4548` / `4548` | 直接指定 EPSG |

### 关于输出坐标系

- **KML / GeoJSON 一律输出 WGS84**。KML 规范只认 WGS84；
  GeoJSON 依 RFC 7946 默认 CRS 也是 WGS84，写投影坐标下游几乎必踩坑。
- **想保留高斯投影请用 SHP**：每个 shp 会附带 `.prj`，ArcMap/QGIS 打开
  直接识别为 `CGCS2000_3_Degree_GK_CM_117E`，不会弹「未知坐标系」。

## 已验证案例（某工厂地形图）

一张 20MB 的 CASS 地形图 DXF（13 个标准图层、约 1.9 万要素）实测：

- 坐标系判定为 **CGCS2000 高斯-克吕格 3 度带、中央子午线 105°E**
  （`cgcs2000-3-105`，EPSG:4544）——坐标范围 (580k, 3610k) 反算落到
  某工厂 (105.86°E, 32.61°N)，吻合。
- `--layer-map cass` 后 12 个数据图层**全部命中语义**（居民地/道路/管线/
  水系/植被/高程点/等高线/地貌/独立地物/图廓/辅助），仅 AutoCAD 默认
  图层 `0` 落 unknown（符合预期）。
- KML/GeoJSON 自动转 WGS84（Google Earth 直接可开）；SHP 保留高斯投影并
  带 `.prj`（`CGCS2000_3_Degree_GK_CM_105E`），ArcMap/QGIS 直接识别。

```bash
plotsmith convert 某工厂地形图.dxf factory.kml \
    --src-cs cgcs2000-3-105 --layer-map cass
```

## 实现说明：高斯-克吕格的两道坑

1. **带号版 EPSG 在某些 proj 构建下反算返回 `inf`**（如 EPSG:4527、4498）。
   所以 `crs_from_spec()` 采用「标准 EPSG 优先 → 反算自检 → PROJ 字符串兜底」：
   先试标准 EPSG 并用样本点做一次真实反算体检，不通过就用 `+proj=tmerc`
   字符串构造。代价是几毫秒，换来的是不会静默产出 `inf` 坐标。
2. **`get_points("xy")` 返回的是元组，不是 Vec 对象**；
   而 `LINE` 的 `start/end` 是 `Vec3`，切片 `[:2]` 在 ezdxf 1.4.x 上会炸；
   `POLYLINE` 的顶点在 ezdxf 1.4.x 里是属性 `e.vertices`（不是方法）。
   提取点时统一按类型分别处理，见 `convert._entity_points()`。

## 已知限制

- DWG 不可直读（AutoCAD 私有格式），需 `dwg2dxf` 预转。
- 支持实体：LINE / LWPOLYLINE / POLYLINE / POINT / CIRCLE / ARC / TEXT / INSERT；
  CIRCLE、ARC 目前取圆心转点，未做圆弧离散化。
- 属性只带图层语义，不解析块属性、扩展数据（XData）。
- `validate` 命令暂为占位。

## 项目来源

本工具是「Codex for Open Source」申请的真实维护项目：作者为工厂总图规划师，
日常处理 DWG↔GIS 互转与坐标系校正。API 额度用于驱动 LLM 辅助的 CAD 图层
自动语义识别（`map-layers suggest`，可选启用）。

## 开发

```bash
pip install -e ".[dev]"
pytest -q
```

## 许可

MIT

## 社区 / Community

- CSDN 技术博客：https://blog.csdn.net/flynet123/article/details/166137434
- 知乎专栏：https://zhuanlan.zhihu.com/p/2085022332368832154
- 掘金：https://juejin.cn/post/7687446787749609478

欢迎在上面平台交流使用心得，或直接在 GitHub 提 issue / PR。如果本工具对你的总图 / 测绘工作有帮助，欢迎点个 Star ⭐。
