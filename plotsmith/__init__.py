"""plotsmith — 工厂总图规划师的智能格式互转工具（零 GDAL 纯 Python）。

核心差异化（护城河）：
1. 中文坐标系一键处理（CGCS2000 / 北京54 / 西安80 / 高斯克吕格分带）
2. 总图图层语义映射（CAD 图层名 -> 有意义的 GIS 要素类 + 中文标签）

设计原则：不依赖 GDAL/ogr2ogr，全部用纯 Python 库（ezdxf / shapely /
pyproj / pyshp），终端用户免装 GDAL。
"""

__version__ = "0.1.0"
