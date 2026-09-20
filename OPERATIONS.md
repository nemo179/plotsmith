# plotsmith / 总图匠 — 操作手册

一份能照着敲的实操指南。覆盖：本地跑通 → 接真实 DWG → 自定义图层 → 上 GitHub → 如实申请 Codex for Open Source。
本机环境已就绪，下面命令在本机可直接运行；换机器按「环境准备」一节重建即可。

> **用什么终端**：本手册命令均为 bash 语法（变量 `$PY`、`<<'EOF'` heredoc），
> 请在 **Git Bash** 或 **WorkBuddy 内置终端**（默认即 bash）里运行，直接复制粘贴即可。
> 若用 Windows 的 `cmd.exe`，需改写为 `set PY=...` + `%PY%` 形式、路径用反斜杠，
> 且 heredoc 不支持（`.gitignore` 等那段用记事本手动建文件）。

---

## 0. 环境准备（本机已装好，换机器照做）

本项目用 WorkBuddy 受管 Python venv，免污染系统。

```bash
# 受管 venv 的 python（本机路径）
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 进入项目目录
cd C:/Users/Administrator/WorkBuddy/2026-08-12-08-47-13/plotsmith

# 装核心依赖（都有 wheel，免编译）
"$PY" -m pip install -q ezdxf shapely pyproj pyshp click pyyaml

# 可编辑安装（之后就能直接敲 plotsmith 命令，而非 python -m plotsmith.cli）
"$PY" -m pip install -e .

# 跑测试确认没问题（应有 7 项全绿）
"$PY" -m pytest -q
```

> 没装 `requests` 也能正常转换；只有 `map-layers suggest`（LLM 图层建议）才需要：`"$PY" -m pip install -e ".[llm]"`。

---

## 1. 本地跑通（先用自带样例验证）

```bash
# 1) 生成一份样例总图 DXF（含给水/建筑/设备/围墙等 7 个专业图层）
"$PY" examples/make_sample_dxf.py        # 生成 examples/plant.dxf

# 2) DXF -> KML：自动转 WGS84，Google Earth 直接可开
"$PY" -m plotsmith.cli convert examples/plant.dxf examples/plant.kml --src-cs cgcs2000-3-117

# 3) DXF -> SHP：保留高斯投影，按点/线/面分文件，自动写 .prj
"$PY" -m plotsmith.cli convert examples/plant.dxf examples/shpout --to shp \
    --src-cs cgcs2000-3-117 --dst-cs cgcs2000-3-117

# 4) DXF -> GeoJSON（同样强制 WGS84）
"$PY" -m plotsmith.cli convert examples/plant.dxf examples/plant.geojson --src-cs cgcs2000-3-117
```

期望结果：`plant.kml` 里坐标是真实经纬度（约 117.0, 36.13）；`shpout/` 下出现 `points.shp / lines.shp / polygons.shp` 及其 `.prj`，ArcMap/QGIS 打开识别为 `CGCS2000_3_Degree_GK_CM_117E`；7 个图层语义全部命中，无 `unknown`。

---

## 2. 接你手上的真实 DWG（关键一步，别人替不了）

DWG 是 AutoCAD 私有格式，本工具**不能直接读**，需先转 DXF：

```bash
# 方案 A：LibreDWG 的 dwg2dxf（免费、命令行）
#   本仓库已内置一份：_tools/dwg2dxf.exe（来自 LibreDWG 0.14 win64 预编译包）
#   也可自行下载：https://github.com/LibreDWG/LibreDWG/releases
_tools/dwg2dxf.exe 你的总图.dwg -o 你的总图.dxf
#   ⚠ dwg2dxf 是 MinGW 版，中文路径参数会崩，先用 ASCII 路径（如先拷到 _work/src.dwg）

# 方案 B：你本就有 AutoCAD / 中望 / 浩辰，直接「另存为 DXF」即可，跳过上面
```

> **⚠ 加密 / 口令保护的 DWG 打不开**：有些总图是 AutoCAD 口令保护或第三方
> 「图纸加密」插件存的，整文件是密文，文件头没有标准的 `AC10xx` 标记。
> 这类文件 LibreDWG / dwg2dxf 读不出合法结构会直接崩溃（RC 0xC0000409），
> **任何开源工具都解不开**。只能回原软件处理：
> 1. 用生成它的 CAD（AutoCAD / Civil 3D / CASS / 中望 / 天正…）打开，按提示输口令；
> 2. 「文件 → 另存为」选 **DXF**（建议 AutoCAD 2018 / R2018 或更低版本，兼容性最好），
>    保存时**不要设口令**；若是天正图，用「文件布图 → 整图导出」成 T3/DXF 更稳；
> 3. 把这份**未加密**的 DXF 交回来，本工具立刻能跑（list_layers + convert + 补模板）。
> 判断方法：用编辑器/Python 看文件头 16 字节，正常 DWG 以 `AC10` 开头；
> 若是高熵乱码、200KB 内找不到 `ACADVER`，基本就是加密了。

转好 DXF 后：

```bash
# 先看一下里面有哪些图层（核对和内置模板的契合度）
"$PY" -m plotsmith.cli convert 你的总图.dxf NUL --src-cs cgcs2000-3-117   # 仅列出图层用下面更准：
"$PY" - <<'PY'
from plotsmith import convert
print(convert.list_layers("你的总图.dxf"))
PY

# 转 KML 看效果（坐标系务必填对你项目实际用的带号，详见第 3 节）
"$PY" -m plotsmith.cli convert 你的总图.dxf 输出.kml --src-cs cgcs2000-3-117
```

**坐标系确认（最容易出错）**：工厂总图常用 3 度带。看你图纸标题栏或测图说明里写的「中央子午线」或「带号」：
- 写「117°」或「第 39 带」→ `--src-cs cgcs2000-3-117`
- 拿不准就用 `plotsmith coords epsg --central 117 --band 3` 反查（117°→EPSG:4548）

**自己也能反推坐标系**：用下面的小脚本看坐标范围。若 X 在 38 万~62 万、Y 在几百万（如 580488, 3609788），就是高斯投影、假东 500000；中央子午线 = 把厂区大致经度按 3° 取整（某厂区 105.8°E → `cgcs2000-3-105`）；Y/1e6 约 = 纬度（3609788 → 32.6°N）。转完用 Google Earth 打开 KML，落点对的就说明 CS 没填错。

**地形图（南方 CASS 标准图层码）记得加 `--layer-map cass`**：CASS 用 JMD/DLSS/GXYZ/SXSS/ZBTZ 等 4 字母码，和总图模板（DL-SS/JZ/SB…）不是一套。内置 `cass` 预设专门覆盖这些，否则会大量落 `unknown`。

若 KML 在 Google Earth 上偏了几百米甚至几千公里，99% 是坐标系/带号填错，先核对这里。

---

## 3. 坐标系速查

| 写法 | 含义 |
| --- | --- |
| `wgs84` | WGS 84（EPSG:4326），天地图/Google 底图 |
| `cgcs2000` | 2000 国家大地坐标系（EPSG:4490），地理坐标 |
| `beijing54` / `xian80` | 北京 54 / 西安 80 |
| `cgcs2000-3-117` | CGCS2000 高斯-克吕格 **3 度带**，中央子午线 117°E |
| `cgcs2000-6-117` | CGCS2000 高斯-克吕格 **6 度带**，中央子午线 117°E |
| `epsg:4548` / `4548` | 直接指定 EPSG |

```bash
"$PY" -m plotsmith.cli coords list                 # 列出全部预设
"$PY" -m plotsmith.cli coords epsg --central 117 --band 3   # -> EPSG:4548
```

> 重要约定：**KML / GeoJSON 一律输出 WGS84**（规范与 RFC 7946 要求）。想保留高斯投影请用 SHP（带 `.prj`）。不要把投影坐标硬塞进 GeoJSON，下游必踩坑。

---

## 4. 自定义图层语义模板（让工具认你单位的图层命名）

内置模板有 25 条总图规则，但**每个设计院图层命名习惯不同**。把它导出改成你自己的：

```bash
# 1) 导出可编辑模板（总图，默认）
"$PY" -m plotsmith.cli map-layers init --output tuzhi_layers.yaml

# 1b) 若是地形图（CASS 标准图层码），导出 CASS 模板更直接
"$PY" -m plotsmith.cli map-layers init --preset cass --output cass_layers.yaml
#     转换时直接用内置预设名即可，无需导出：--layer-map cass

# 2) 编辑 tuzhi_layers.yaml，规则语法：
#    match: 匹配串；type: exact | prefix | regex
#    feature_class: 英文要素类；category: 大类；label: 中文标签
#    匹配顺序：exact -> prefix -> regex，命中即返回；都不中走 default
#    建议：具体图层放前面，注记类（文字/标高/索引）放最后，免得吞掉实体图层
```

示例（把你单位的「JS-厂房」也认成建筑）：

```yaml
rules:
  - match: "JS-"
    type: prefix
    feature_class: building
    category: building
    label: 建筑单体
default:
  feature_class: unknown
  category: other
  label: 未分类
```

```bash
# 3) 用自定义模板转换
"$PY" -m plotsmith.cli convert 你的总图.dxf 输出.kml --layer-map tuzhi_layers.yaml --src-cs cgcs2000-3-117
```

把调好的 `tuzhi_layers.yaml` 提交进仓库，就是你对这个项目最实在的贡献——也是申请 Codex 时最有说服力的「真实维护」证据。

---

## 5. 提交到 GitHub（让项目有个家）

```bash
cd C:/Users/Administrator/WorkBuddy/2026-08-12-08-47-13/plotsmith

# 1) 写 .gitignore（清掉缓存和样例产物）
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.pytest_cache/
examples/plant.dxf
examples/plant.kml
examples/plant.geojson
shpout/
_demo/
EOF

# 2) 初始化并首个 commit
git init
git add .
git commit -m "feat: 总图匠 MVP — 零GDAL的DWG/DXF→KML/SHP/GeoJSON互转，含中文坐标系与总图图层语义"

# 3) 在 github.com 新建空仓库（不要勾 README），然后关联推送
git branch -M main
git remote add origin https://github.com/你的用户名/plotsmith.git
git push -u origin main
```

> `plotsmith-plan.md`（方案文档）在仓库**外层**工作区，是给 AI 跨设备续作用的，建议**不要**塞进开源仓库；仓库里用 README 的「项目来源」段落说明即可。

---

## 6. 如实申请 Codex for Open Source

入口：https://github.com/features/codex 或 OpenAI 官方「Codex for Open Source」页面（以当时页面为准）。

**核心原则：如实。** 你就是这个项目的真实维护者，按下面写即可，不必夸大：

1. **项目是什么**：工厂总图规划师的智能格式互转 CLI，零 GDAL 纯 Python。
2. **为什么真实有用**：你日常工作就是 DWG↔GIS 互转 + 坐标系校正，通用工具（GDAL/QGIS）装 GDAL 坑、图层名对规划师没意义。本项目解决这两个痛点。
3. **你已做了什么**（诚实列）：
   - 选定方向、验证工具链（本机无 GDAL，改用 ezdxf/shapely/pyproj/pyshp）
   - 写完 MVP：convert/coords/map-layers 三条命令 + 25 条总图图层规则 + 5 项测试
   - 踩过的真实坑（高斯带反算 inf、ezdxf 取值两套逻辑、DBF 字段截断）已修复并写进测试
4. **申请额度打算用来做什么**（最该具体）：
   - 驱动 `map-layers suggest`：用 LLM 自动识别你单位/其他院非常规 CAD 图层名 → 建议语义映射
   - 后续支柱一：三维总平融合（Cesium 3D Tiles，地形+设计模型叠加）
   - 后续支柱二：总图规范校验（GB50187 总图布置、防火间距）
5. **不要写**：「我打算做一个大项目」却没代码；或把别人的仓库说成自己的。当前仓库已有可运行的 MVP，这就是你申请的底气。

提交后保持仓库活跃（真实提交、回应 issue），比一次性铺量更重要。

---

## 7. 后续路线（申请的「下一步」要写清楚）

- **Pillar 2 — 三维融合**：读 Terrain/DEM + 设计模型，输出 Cesium 3D Tiles，总平与地形叠加看效果。
- **Pillar 3 — 规范校验**：GB50187 总图布置、建规防火间距自动查，输出违规清单。
- **健壮性**：CIRCLE/ARC 圆弧离散化、块属性(XData)解析、DWG 直读（接 LibreDWG 自动预转）。

---

## 附：常见报错速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'requests'` | 没装 LLM 可选依赖 | 核心转换不受影响；要 suggest 就 `pip install -e ".[llm]"` |
| KML 坐标偏到海外/几百公里 | 坐标系带号填错 | 用 `coords epsg` 核对中央子午线 |
| 某图层显示 `unknown` | 内置模板没覆盖你单位命名 | `map-layers init` 导出模板补规则 |
| `dwg` 直接转换被拒 | DWG 私有格式 | 先 `dwg2dxf` 转 DXF，或 AutoCAD 另存 DXF |
| dwg2dxf 直接崩溃（RC 0xC0000409）/ 抽不出图层 | DWG 被加密或口令保护（整文件密文，无 `AC10xx` 头） | 用原软件输口令后「另存为」**未加密** DXF（R2018 或更低），再交回本工具；开源工具解不开加密 DWG |
