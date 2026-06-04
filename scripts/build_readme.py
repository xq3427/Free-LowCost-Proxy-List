# -*- coding: utf-8 -*-
"""
根据 data/providers.yml 同步生成中文版 README.md 和英文版 README.en.md。

功能：
1. 生成中文版 README.md；
2. 生成英文版 README.en.md；
3. 生成首页汇总表；
4. 为每个服务商生成独立详情卡片；
5. 每个服务商详情下方展示套餐截图；
6. 检查截图文件是否存在；
7. 支持中英文字段，英文缺失时自动回退到中文字段。

注意：
不要在 providers.yml、README.md 或 README.en.md 中填写节点订阅链接、账号密码、破解资源等敏感内容。
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any, Dict, List


try:
    import yaml
except ImportError as exc:
    raise SystemExit("缺少依赖 PyYAML，请执行：pip install pyyaml") from exc


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "providers.yml"
README_ZH_FILE = ROOT / "README.md"
README_EN_FILE = ROOT / "README.en.md"


def load_yaml() -> List[Dict[str, Any]]:
    """
    读取 providers.yml。
    """
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"数据文件不存在：{DATA_FILE}")

    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    providers = data.get("providers", [])

    if not isinstance(providers, list):
        raise ValueError("providers 字段必须是列表")

    return providers


def md_escape(value: Any) -> str:
    """
    转义 Markdown 表格中的特殊字符。
    """
    if value is None:
        return ""

    text = str(value)
    text = text.replace("|", "\\|")
    text = text.replace("\n", "<br>")
    return text


def slugify(text: str) -> str:
    """
    生成稳定的 Markdown 锚点。
    优先使用 providers.yml 中的 id 字段，避免中文标题锚点不稳定。
    """
    text = str(text).strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff\-]", "", text)
    return text or "unknown"


def get_provider_id(item: Dict[str, Any]) -> str:
    """
    获取服务商 ID。
    """
    provider_id = str(item.get("id", "")).strip()

    if provider_id:
        return slugify(provider_id)

    name = str(item.get("name", "unknown")).strip()
    return slugify(name)


def get_value(item: Dict[str, Any], key: str, lang: str) -> Any:
    """
    根据语言读取字段。

    lang = "zh" 时读取 key；
    lang = "en" 时优先读取 key_en，如果没有则回退读取 key。
    """
    if lang == "en":
        en_key = f"{key}_en"
        value = item.get(en_key)

        if value not in (None, ""):
            return value

    return item.get(key, "")


def list_to_text(value: Any, lang: str) -> str:
    """
    将列表转换为 Markdown 中适合展示的字符串。
    """
    if value is None:
        return ""

    if isinstance(value, list):
        separator = "、" if lang == "zh" else ", "
        return separator.join(str(item) for item in value)

    return str(value)


def get_price_text(item: Dict[str, Any], lang: str) -> str:
    """
    生成价格文本。
    """
    price = item.get("lowest_price_cny", "")
    cycle = get_value(item, "billing_cycle", lang)

    if price == "" or price is None:
        return "未知" if lang == "zh" else "Unknown"

    try:
        price_float = float(price)
    except Exception:
        return str(price)

    if price_float == 0:
        return "免费/试用" if lang == "zh" else "Free / Trial"

    if lang == "zh":
        if cycle:
            return f"{price:g} 元/{cycle}"
        return f"{price:g} 元"

    if cycle:
        return f"CNY {price:g}/{cycle}"

    return f"CNY {price:g}"


def sort_providers(providers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按最低价格从低到高排序。
    """
    def key_func(item: Dict[str, Any]) -> float:
        price = item.get("lowest_price_cny", 999999)

        try:
            return float(price)
        except Exception:
            return 999999

    return sorted(providers, key=key_func)


def screenshot_exists(screenshot_path: str) -> bool:
    """
    检查截图文件是否存在。
    """
    if not screenshot_path:
        return False

    path = ROOT / screenshot_path
    return path.exists() and path.is_file()


def build_summary_table(providers: List[Dict[str, Any]], lang: str) -> str:
    """
    生成汇总表。
    """
    if lang == "zh":
        headers = [
            "序号",
            "名称",
            "类型",
            "最低价格",
            "流量",
            "免费试用",
            "节点地区",
            "最后检查",
            "详情",
        ]
        detail_text = "查看"
    else:
        headers = [
            "No.",
            "Name",
            "Category",
            "Lowest Price",
            "Traffic",
            "Free Trial",
            "Node Regions",
            "Last Checked",
            "Details",
        ]
        detail_text = "View"

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|---:|---|---|---:|---|---|---|---|---|")

    for idx, item in enumerate(providers, start=1):
        provider_id = get_provider_id(item)
        name = md_escape(get_value(item, "name", lang))
        category = md_escape(get_value(item, "category", lang))
        price = md_escape(get_price_text(item, lang))
        traffic = md_escape(get_value(item, "traffic", lang))
        free_trial = md_escape(get_value(item, "free_trial", lang))
        node_regions = md_escape(list_to_text(get_value(item, "node_regions", lang), lang))
        last_checked = md_escape(item.get("last_checked", ""))

        lines.append(
            f"| {idx} | {name} | {category} | {price} | {traffic} | "
            f"{free_trial} | {node_regions} | {last_checked} | "
            f"[{detail_text}](#{provider_id}) |"
        )

    return "\n".join(lines)


def build_provider_detail(item: Dict[str, Any], index: int, lang: str) -> str:
    """
    生成单个服务商详情。
    """
    provider_id = get_provider_id(item)
    name = md_escape(get_value(item, "name", lang))
    website = str(item.get("website", "")).strip()

    category = md_escape(get_value(item, "category", lang))
    price = md_escape(get_price_text(item, lang))
    traffic = md_escape(get_value(item, "traffic", lang))
    free_trial = md_escape(get_value(item, "free_trial", lang))

    protocols = md_escape(list_to_text(get_value(item, "protocols", lang), lang))
    node_regions = md_escape(list_to_text(get_value(item, "node_regions", lang), lang))
    payment = md_escape(list_to_text(get_value(item, "payment", lang), lang))

    speed_limit = md_escape(get_value(item, "speed_limit", lang))
    device_limit = md_escape(get_value(item, "device_limit", lang))
    registration = md_escape(get_value(item, "registration", lang))
    last_checked = md_escape(item.get("last_checked", ""))
    screenshot = str(item.get("screenshot", "")).strip()
    screenshots = item.get("screenshots")

    if isinstance(screenshots, list):
        screenshot_paths = [str(path).strip() for path in screenshots if str(path).strip()]
    elif screenshot:
        screenshot_paths = [screenshot]
    else:
        screenshot_paths = []

    if lang == "zh":
        website_md = f"[访问官网]({md_escape(website)})" if website else "未填写"
        fields = {
            "类型": category,
            "官网": website_md,
            "最低价格": price,
            "流量": traffic,
            "免费试用": free_trial,
            "协议": protocols,
            "节点地区": node_regions,
            "支付方式": payment,
            "限速说明": speed_limit,
            "设备限制": device_limit,
            "注册状态": registration,
            "最后检查": last_checked,
        }
        screenshot_title = "套餐截图："
        missing_screenshot_prefix = "截图文件未找到"
        no_screenshot = "暂未提供截图。"
        back_top = "返回顶部"
        screenshot_alt = f"{name} 套餐截图"
    else:
        website_md = f"[Official Website]({md_escape(website)})" if website else "Not provided"
        fields = {
            "Category": category,
            "Website": website_md,
            "Lowest Price": price,
            "Traffic": traffic,
            "Free Trial": free_trial,
            "Protocols": protocols,
            "Node Regions": node_regions,
            "Payment Methods": payment,
            "Speed Limit": speed_limit,
            "Device Limit": device_limit,
            "Registration": registration,
            "Last Checked": last_checked,
        }
        screenshot_title = "Plan screenshot:"
        missing_screenshot_prefix = "Screenshot file not found"
        no_screenshot = "No screenshot provided."
        back_top = "Back to top"
        screenshot_alt = f"{name} plan screenshot"

    lines = []
    lines.append(f'<a id="{provider_id}"></a>')
    lines.append("")
    lines.append(f"## {index}. {name}")
    lines.append("")
    lines.append("| 字段 | 内容 |" if lang == "zh" else "| Field | Value |")
    lines.append("|---|---|")

    for key, value in fields.items():
        lines.append(f"| {key} | {value} |")

    lines.append("")
    lines.append(f"**{screenshot_title}**")
    lines.append("")

    if screenshot_paths:
        for idx, screenshot_path in enumerate(screenshot_paths, start=1):
            if screenshot_exists(screenshot_path):
                alt = screenshot_alt if len(screenshot_paths) == 1 else f"{screenshot_alt} {idx}"
                lines.append(f"![{md_escape(alt)}]({md_escape(screenshot_path)})")
            else:
                lines.append(f"> {missing_screenshot_prefix}: `{md_escape(screenshot_path)}`")
    else:
        lines.append(f"> {no_screenshot}")

    lines.append("")
    lines.append(f"[{back_top}](#top)")
    lines.append("")

    return "\n".join(lines)


def build_readme_zh(providers: List[Dict[str, Any]]) -> str:
    """
    生成中文版 README。
    """
    today = datetime.date.today().isoformat()
    providers = sort_providers(providers)

    summary_table = build_summary_table(providers, lang="zh")
    details = "\n---\n\n".join(
        build_provider_detail(item, index, lang="zh")
        for index, item in enumerate(providers, start=1)
    )

    return f"""<a id="top"></a>

# 免费低价代理服务信息统计

[English Version](README.en.md)

本仓库用于整理公开可查询的免费或低价代理服务信息，重点记录服务商官网、套餐价格、流量、试用、节点地区、支付方式和套餐截图。

## 重要说明

本仓库只做公开信息整理，不提供、不存储、不传播以下内容：

- 节点订阅链接；
- 账号密码；
- 邀请码倒卖；
- 破解资源；
- 非公开接口；
- 绕过限制的具体教程；
- 任何违反当地法律法规或平台规则的内容。

所有价格、流量、节点地区和截图均可能随服务商调整而变化，请以官网公开页面为准。

## 数据更新时间

最后自动生成时间：`{today}`

## 汇总表

{summary_table}

---

# 服务商详情

{details}

---

# 字段说明

| 字段 | 含义 |
|---|---|
| 名称 | 服务商名称 |
| 类型 | 免费试用、低价、长期套餐等 |
| 官网 | 公开主页链接 |
| 最低价格 | 当前公开页面可见的最低价格 |
| 流量 | 套餐流量 |
| 免费试用 | 是否支持免费试用 |
| 协议 | 公开页面展示的协议类型 |
| 节点地区 | 公开展示的节点地区 |
| 支付方式 | 公开展示的支付方式 |
| 限速说明 | 是否公开限速信息 |
| 设备限制 | 是否限制同时在线设备数 |
| 注册状态 | 是否开放注册 |
| 最后检查 | 最近一次人工核验日期 |
| 套餐截图 | 对应套餐页截图，需注意打码隐私信息 |

# 免责声明

本仓库内容仅用于公开信息整理和价格对比，不构成购买建议、使用建议或安全承诺。服务可用性、价格、协议、节点地区、支付方式可能随时变化，请以服务商官网公开信息为准。
"""


def build_readme_en(providers: List[Dict[str, Any]]) -> str:
    """
    生成英文版 README。
    """
    today = datetime.date.today().isoformat()
    providers = sort_providers(providers)

    summary_table = build_summary_table(providers, lang="en")
    details = "\n---\n\n".join(
        build_provider_detail(item, index, lang="en")
        for index, item in enumerate(providers, start=1)
    )

    return f"""<a id="top"></a>

# Free and Low-Cost Proxy Service Index

[中文版](README.md)

This repository collects publicly available information about free or low-cost proxy service providers, including official websites, plan prices, traffic quotas, free trials, node regions, payment methods, and plan screenshots.

## Important Notice

This repository is only for public information aggregation. It does not provide, store, or distribute any of the following:

- Node subscription links;
- Account credentials;
- Invitation code reselling;
- Cracked resources;
- Non-public APIs;
- Step-by-step instructions for bypassing restrictions;
- Any content that violates applicable laws, regulations, or platform rules.

All prices, traffic quotas, node regions, payment methods, and screenshots may change at any time. Please refer to the official public pages of each provider.

## Data Update Time

Last generated on: `{today}`

## Summary Table

{summary_table}

---

# Provider Details

{details}

---

# Field Description

| Field | Description |
|---|---|
| Name | Provider name |
| Category | Free trial, low-cost plan, long-term plan, etc. |
| Website | Public official website |
| Lowest Price | The lowest publicly visible plan price |
| Traffic | Traffic quota of the plan |
| Free Trial | Whether a free trial is available |
| Protocols | Protocol types publicly displayed by the provider |
| Node Regions | Publicly displayed node regions |
| Payment Methods | Publicly displayed payment methods |
| Speed Limit | Whether speed limit information is disclosed |
| Device Limit | Whether simultaneous device limits are disclosed |
| Registration | Whether registration is open |
| Last Checked | Last manual verification date |
| Plan Screenshot | Screenshot of the public plan page, with private information redacted |

# Disclaimer

This repository is only for public information aggregation and price comparison. It does not constitute purchasing advice, usage advice, or any security guarantee. Service availability, prices, protocols, node regions, and payment methods may change at any time. Please refer to the official public information of each provider.
"""


def main() -> None:
    providers = load_yaml()

    readme_zh = build_readme_zh(providers)
    readme_en = build_readme_en(providers)

    with README_ZH_FILE.open("w", encoding="utf-8", newline="\n") as f:
        f.write(readme_zh)

    with README_EN_FILE.open("w", encoding="utf-8", newline="\n") as f:
        f.write(readme_en)

    print(f"README.md 已生成，共统计 {len(providers)} 个服务商。")
    print(f"README.en.md 已生成，共统计 {len(providers)} 个服务商。")


if __name__ == "__main__":
    main()
