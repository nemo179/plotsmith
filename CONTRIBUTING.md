# 贡献指南 / Contributing

感谢你考虑为 **plotsmith / 总图匠** 做贡献！这是一个面向工厂总图规划与测绘的
CAD↔GIS 互转工具，核心约束是**零 GDAL 依赖、纯 Python**。

## 开发环境

需要 Python 3.9+ 与 Git。

```bash
# 克隆
git clone git@github.com:nemo179/plotsmith.git
cd plotsmith

# 安装（含测试/开发依赖）
pip install -e ".[dev]"

# 运行测试
pytest -q
```

核心依赖：`ezdxf` / `shapely` / `pyproj` / `pyshp` / `click` / `pyyaml`
（均有 wheel，免编译）。`requests` 仅在 `map-layers suggest`（LLM 图层建议）时懒加载。

## 提交流程

1. Fork 并新建分支：`git checkout -b fix/xxx` 或 `feat/xxx`。
2. 保持提交小而聚焦，信息用 Conventional Commits 风格
  （`feat:` / `fix:` / `docs:` / `test:` / `refactor:`）。
3. **任何改动都请带上或更新测试**，`pytest -q` 全绿后再提交。
4. 发起 Pull Request，描述「为什么」以及「验证了什么」。

## 如何新增 / 调整图层语义规则

图层语义是 plotsmith 的核心差异点，欢迎补充你所在行业的图层约定：

- 内置预设在 `plotsmith/presets/`（`tuzhi_layers.yaml` 总图、`cass_topo_layers.yaml` 南方 CASS）。
- 本地调试可用 `plotsmith map-layers init --preset cass --output my.yaml` 导出模板，
  按需增删规则后 `--layer-map my.yaml` 试用。
- 规则匹配顺序：**exact → prefix → regex**，命中即返回，最后落到 `default`。
- 改完预设请同步更新 `tests/` 里对应的语义断言，防止悄悄退化。

## 设计红线（请勿破坏）

- **不引入 GDAL / OGR 等重依赖**。新增坐标系能力请走 `pyproj` + PROJ 字符串。
- **高斯-克吕格带号版 EPSG 必须做反算自检**：部分 proj 构建下反算返回 `inf`，
  请用 `coords.crs_from_spec()` 的「标准 EPSG 优先 → 反算自检 → PROJ 字符串兜底」路径。
- **KML / GeoJSON 一律输出 WGS84**；要保留高斯投影请用 SHP（并写 `.prj`）。

## 行为准则

请友好、就事论事地交流。本仓库采用
[Contributor Covenant](https://www.contributor-covenant.org/) 行为准则。
