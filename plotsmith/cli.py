"""plotsmith 命令行入口。"""

import click

from . import coords, layermap, convert
from .llm_map import suggest_mapping


@click.group()
@click.version_option()
def cli():
    """plotsmith — 工厂总图规划智能格式互转工具（零 GDAL 纯 Python）。"""


@cli.command()
@click.argument("input", type=click.Path(exists=True))
@click.argument("output", type=click.Path())
@click.option("--from", "src_fmt", default="dxf", show_default=True)
@click.option("--to", "dst_fmt", default=None, help="kml/shp/geojson；默认按 output 扩展名")
@click.option("--src-cs", default="wgs84", show_default=True, help="源坐标系预设名或 epsg:XXXX")
@click.option("--dst-cs", default="wgs84", show_default=True, help="目标坐标系预设名或 epsg:XXXX")
@click.option("--layer-map", default=None, help="图层语义映射：YAML 路径，或预设名 tuzhi/cass（默认 tuzhi）")
def convert_cmd(input, output, src_fmt, dst_fmt, src_cs, dst_cs, layer_map):
    """互转：DXF -> SHP/KML/GeoJSON（DWG 需先 dwg2dxf 转 DXF）。"""
    fmt = dst_fmt or convert._ext(output)
    if fmt not in ("kml", "shp", "geojson"):
        raise click.BadParameter("输出格式需为 kml / shp / geojson")
    if src_fmt == "dwg":
        click.echo("DWG 是 AutoCAD 私有格式，请先经 LibreDWG 的 dwg2dxf 转成 DXF 后再转换。")
        return
    n = convert.convert(input, output, src_cs, dst_cs, layer_map, fmt)
    click.echo(f"完成：写出 {n} 个要素到 {output}")


@cli.command("coords")
@click.argument("action", type=click.Choice(["list", "epsg"]))
@click.option("--central", type=float, help="中央子午线（度）")
@click.option("--band", type=click.Choice(["3", "6"]), default="3")
@click.option("--datum", default="cgcs2000")
def coords_cmd(action, central, band, datum):
    """列出坐标系预设，或计算高斯克吕格带 EPSG。"""
    if action == "list":
        for k, v in coords.list_presets().items():
            click.echo(f"{k:20s} -> EPSG:{v}")
    else:
        if central is None:
            raise click.BadParameter("--central 必填")
        epsg = coords.gauss_epsg(central, int(band), datum)
        click.echo(f"{datum} 高斯{band}度带 中央子午线{central}° -> EPSG:{epsg}")


@cli.command("map-layers")
@click.argument("action", type=click.Choice(["init", "suggest"]))
@click.option("--output", default="tuzhi_layers.yaml")
@click.option("--preset", default="tuzhi", help="init 用模板：tuzhi（总图）或 cass（CASS 地形图）")
@click.option("--dxf", default=None, help="suggest 用：待识别的 DXF")
@click.option("--api-key", envvar="OPENAI_API_KEY")
@click.option("--base-url", default=None, envvar="OPENAI_BASE_URL")
def map_layers_cmd(action, output, preset, dxf, api_key, base_url):
    """生成图层映射模板，或用 LLM 建议未知图层语义。"""
    if action == "init":
        layermap.write_template(output, preset)
        click.echo(f"已生成图层映射模板（{preset}）：{output}")
        return
    if not dxf or not api_key:
        raise click.BadParameter("suggest 需要 --dxf 与 API key（OPENAI_API_KEY）")
    layers = convert.list_layers(dxf)
    click.echo(suggest_mapping(layers, api_key, base_url))


@cli.command()
@click.argument("gis", type=click.Path(exists=True))
def validate(gis):
    """基础几何校验占位（自相交/空几何，后续补全）。"""
    click.echo("validate: 占位命令，后续补全自相交/环方向检查。")


if __name__ == "__main__":
    cli()
