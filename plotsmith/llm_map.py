"""可选 LLM 图层语义建议（OpenAI 兼容接口，含 DeepSeek）。

仅在用户显式提供 API key 时启用，不强制依赖。用于把未知 CAD 图层名
映射成总图语义——这也是 Codex for OSS 申请中 API 额度的诚实用途之一。
"""

import os


def suggest_mapping(layers, api_key, base_url=None, model="deepseek-chat"):
    # 延迟导入：requests 为可选依赖，仅在真正调用 LLM 时才需要，
    # 避免核心 CLI（坐标转换/格式互转）因未装 requests 而崩溃。
    import requests

    base = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
    prompt = (
        "你是工厂总图规划领域专家。下面是某 CAD 图纸里的图层名列表，请为每个图层"
        "推断其总图语义，返回 YAML 列表，每项含 layer / feature_class / category / label"
        "（label 用中文）。图层名：\n" + "\n".join(layers)
    )
    resp = requests.post(
        base + "/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
