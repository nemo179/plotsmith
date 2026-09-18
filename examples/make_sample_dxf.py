"""生成一份模拟工厂总图 DXF，供试跑与贡献者自测。

坐标按 CGCS2000 3 度带（中央子午线 117°E）的高斯投影取值设定：
东移 500km（x_0=500000）、y≈4000km，对应真实经度 117°E 附近。

用法：
    python examples/make_sample_dxf.py [输出目录]
    plotsmith convert 输出目录/plant.dxf plant.kml --src-cs cgcs2000-3-117
"""

import os
import sys

import ezdxf

# (图层名, 实体创建函数) —— 图层名刻意覆盖总图各专业，用来验证语义映射
ITEMS = [
    # 给排水管线（线）
    ("DL-SS-01", lambda msp: msp.add_line((500000, 4000000), (500100, 4000000))),
    # 厂房建筑（闭合多段线 -> 面）
    (
        "JZ-01",
        lambda msp: msp.add_lwpolyline(
            [
                (500000, 4000000),
                (500000, 4000100),
                (500200, 4000100),
                (500200, 4000000),
                (500000, 4000000),
            ]
        ),
    ),
    # 设备点位
    ("SB-01", lambda msp: msp.add_point((500050, 4000050))),
    # 围墙
    ("WQ-01", lambda msp: msp.add_lwpolyline([(500000, 4000000), (500300, 4000000)])),
    # 铁路
    ("TL-01", lambda msp: msp.add_line((500000, 4000300), (500400, 4000300))),
    # 消防管线
    ("XF-01", lambda msp: msp.add_line((500000, 4000200), (500250, 4000200))),
    # 绿化用地
    (
        "LH-01",
        lambda msp: msp.add_lwpolyline(
            [
                (500000, 4000400),
                (500000, 4000500),
                (500100, 4000500),
                (500100, 4000400),
                (500000, 4000400),
            ]
        ),
    ),
]


def build(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for layer, maker in ITEMS:
        e = maker(msp)
        e.dxf.layer = layer
    doc.saveas(path)
    return path


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)
    p = build(os.path.join(out_dir, "plant.dxf"))
    print("已生成:", p, f"({len(ITEMS)} 个实体)")


if __name__ == "__main__":
    main()
