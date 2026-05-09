# backend/services/radar_service/push_generator.py
"""
LLM 邮件内容生成模块（固定模板 + 结构化数据方案）

- LLM 生成结构化 JSON 数据（保证每次格式一致）
- 固定 HTML 模板渲染，保证邮件样式统一
- 支持所有主流邮件客户端（table 布局 + 内联 CSS）
"""
import asyncio
import json
import datetime
from typing import Optional

from core.logger import get_logger

logger = get_logger("radar.push_generator")

# LLM 使用默认模型（DeepSeek，engine 参数为空时默认走 deepseek 分支）
DEFAULT_ENGINE = ""

# 平台名映射（多处使用）
PLATFORM_MAP = {"wb": "微博", "xhs": "小红书", "bili": "B站", "zhihu": "知乎",
                "dy": "抖音", "ks": "快手", "tieba": "贴吧"}

# 每日简报用的 emoji 平台名映射
PLATFORM_EMOJI_MAP = {"wb": "📱 微博", "xhs": "📕 小红书", "bili": "📺 B站", "zhihu": "💬 知乎",
                      "dy": "🎵 抖音", "ks": "🎬 快手", "tieba": "💬 贴吧"}

# ============================================================
# 固定 HTML 模板（简约高级，支持基础交互）
# ============================================================

PUSH_HTML_TEMPLATE = """
<!-- MediaRadar 舆情预警邮件 -->
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="max-width:620px;margin:0 auto;font-family:'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;
              background:#e8ecf1;">
  <!-- 顶部深色标题栏 -->
  <tr>
    <td style="padding:0;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="padding:28px 32px 24px 32px;background:{banner_bg};">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <!-- 左侧风险标签 -->
                <td style="vertical-align:middle;padding-right:16px;">
                  <span style="display:inline-block;padding:4px 10px;background:rgba(255,255,255,0.15);
                               border-radius:4px;font-size:11px;font-weight:600;color:rgba(255,255,255,0.9);
                               letter-spacing:0.5px;border:1px solid rgba(255,255,255,0.2);">
                    {banner_icon}&nbsp;{banner_label}
                  </span>
                </td>
                <td align="right" style="vertical-align:middle;">
                  <span style="font-size:11px;color:rgba(255,255,255,0.45);letter-spacing:0.5px;">{generated_date}</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- 主内容区 -->
  <tr>
    <td style="padding:0 20px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:#ffffff;border-radius:0 0 14px 14px;">

        <!-- 关键词标题 -->
        <tr>
          <td style="padding:28px 20px 4px 20px;">
            <p style="margin:0;font-size:24px;font-weight:700;color:#0d1b2a;line-height:1.35;letter-spacing:-0.3px;">
              {keyword}
            </p>
          </td>
        </tr>

        <!-- 统计卡片行 -->
        <tr>
          <td style="padding:0 20px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="margin-top:14px;border-collapse:separate;border-spacing:0 6px;">
              <tr>
                <td width="33%" style="background:#f4f7fb;padding:14px 12px 12px;border-radius:8px;">
                  <p style="margin:0 0 3px;font-size:10px;color:#8a9aaa;letter-spacing:0.8px;text-transform:uppercase;">涉及平台</p>
                  <p style="margin:0;font-size:14px;font-weight:600;color:#1a2c3d;">{platform}</p>
                </td>
                <td width="6"></td>
                <td width="33%" style="background:#f4f7fb;padding:14px 12px 12px;border-radius:8px;">
                  <p style="margin:0 0 3px;font-size:10px;color:#8a9aaa;letter-spacing:0.8px;text-transform:uppercase;">风险等级</p>
                  <p style="margin:0;font-size:14px;font-weight:700;color:{risk_color};">{risk_label}</p>
                </td>
                <td width="6"></td>
                <td width="33%" style="background:#f4f7fb;padding:14px 12px 12px;border-radius:8px;">
                  <p style="margin:0 0 3px;font-size:10px;color:#8a9aaa;letter-spacing:0.8px;text-transform:uppercase;">相关帖子</p>
                  <p style="margin:0;font-size:14px;font-weight:600;color:#1a2c3d;">{post_count} 条</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- 分隔线 -->
        <tr>
          <td style="padding:20px 20px 0;">
            <tr><td style="height:1px;background:#e4eaf2;"></td></tr>
          </td>
        </tr>

        <!-- 核心问题（折叠交互） -->
        <tr>
          <td style="padding:0 20px;">
            <details style="display:block;margin-top:0;" open>
              <summary style="cursor:pointer;user-select:none;padding:16px 0 14px;
                               list-style:none;border-bottom:1px solid #e4eaf2;">
                <span style="font-size:12px;font-weight:600;color:#0d1b2a;letter-spacing:0.3px;">核心问题</span>
                <span id="arrow_core" style="float:right;font-size:11px;color:#8a9aaa;transition:transform 0.2s;">▼</span>
              </summary>
              <div style="padding:16px 0;background:#f0f5fb;border-radius:8px;margin-bottom:10px;">
                <p style="margin:0;font-size:14px;color:#2d3f52;line-height:1.9;">{core_issue}</p>
              </div>
            </details>
          </td>
        </tr>

        <!-- 预警简报（折叠交互） -->
        <tr>
          <td style="padding:0 20px;">
            <details style="display:block;" open>
              <summary style="cursor:pointer;user-select:none;padding:14px 0;
                               list-style:none;border-bottom:1px solid #e4eaf2;">
                <span style="font-size:12px;font-weight:600;color:#0d1b2a;letter-spacing:0.3px;">预警简报</span>
                <span style="float:right;font-size:11px;color:#8a9aaa;">▼</span>
              </summary>
              <div style="padding:16px 0;background:#eef2f7;border-radius:8px;margin-bottom:10px;">
                <p style="margin:0;font-size:13px;color:#2d3f52;line-height:2;white-space:pre-wrap;">{report}</p>
              </div>
            </details>
          </td>
        </tr>

        <!-- 溯源链接（折叠交互） -->
        <tr>
          <td style="padding:0 20px 20px;">
            <details style="display:block;">
              <summary style="cursor:pointer;user-select:none;padding:14px 0;
                               list-style:none;">
                <span style="font-size:12px;font-weight:600;color:#0d1b2a;letter-spacing:0.3px;">溯源链接&nbsp;<span style="font-weight:400;color:#8a9aaa;">({link_count})</span></span>
                <span style="float:right;font-size:11px;color:#8a9aaa;">▶</span>
              </summary>
              <div style="padding:12px 0;background:#f4f7fb;border-radius:8px;">
                {link_items}
              </div>
            </details>
          </td>
        </tr>

      </table>
    </td>
  </tr>

  <!-- 底部 -->
  <tr>
    <td style="padding:20px 20px 28px;">
      <p style="margin:0;text-align:center;font-size:10px;color:#8a9aaa;letter-spacing:0.5px;">
        MediaRadar · 舆情监测系统 · {generated_time}
      </p>
    </td>
  </tr>
</table>
"""


def _build_link_items(urls: list[str]) -> str:
    """构建链接列表 HTML"""
    items = []
    for i, url in enumerate(urls[:10], 1):  # 最多10条
        truncated = url[:70] + "..." if len(url) > 70 else url
        items.append(
            f'<p style="margin:0 0 8px;font-size:12px;line-height:1.5;">'
            f'<a href="{url}" style="color:#1a3a5c;text-decoration:none;">'
            f'<span style="display:inline-block;min-width:18px;height:18px;background:#1a3a5c;color:#fff;text-align:center;'
            f'border-radius:3px;font-size:10px;line-height:18px;margin-right:8px;vertical-align:middle;">{i}</span>'
            f'<span style="color:#2c3e50;font-size:12px;">{truncated}</span></a></p>'
        )
    return "".join(items) if items else '<p style="margin:0;font-size:12px;color:#8a9aaa;padding:8px 0;">暂无链接</p>'


def render_push_html(data: dict) -> str:
    """
    用固定模板渲染预警邮件 HTML。

    data 字段：
        keyword, platform, risk_level, risk_class,
        core_issue, report, post_count, urls, generated_at
    """
    risk_class = data.get("risk_class", "neutral")
    risk_level = data.get("risk_level", 3)

    # 风险等级颜色 + 标签（冷色调高级感）
    risk_meta = {
        "critical": ("#c0392b", "🚨 极高风险"),
        "high": ("#c0392b", "🔴 高风险"),
        "medium": ("#2471a3", "🔵 中风险"),
        "low": ("#1e8449", "🟢 低风险"),
        "neutral": ("#566573", "⚪ 舆情通知"),
    }
    banner_meta = {
        "critical": ("#1a1a2e", "🚨 极高风险预警"),
        "high": ("#16213e", "🔴 高风险预警"),
        "medium": ("#1a3a5c", "🔵 中风险预警"),
        "low": ("#145a32", "🟢 低风险提醒"),
        "neutral": ("#34495e", "⚪ 舆情通知"),
    }

    risk_color, risk_label = risk_meta.get(risk_class, ("#6b7280", "⚪ 舆情通知"))
    banner_bg, banner_label = banner_meta.get(risk_class, ("#6b7280", "⚪ 舆情通知"))

    now = datetime.datetime.now()
    generated_date = now.strftime("%Y-%m-%d")
    generated_time = now.strftime("%Y-%m-%d %H:%M")

    # 平台名处理
    platform_display = PLATFORM_MAP.get(data.get("platform", ""), data.get("platform", "全部平台"))

    # 处理 core_issue 和 report
    core_issue = data.get("core_issue", "无") or "无"
    report = data.get("report", "无") or "无"

    # 如果 core_issue 或 report 太长，在摘要里截断
    if len(core_issue) > 200:
        core_issue = core_issue[:200] + "..."

    html = PUSH_HTML_TEMPLATE.format(
        banner_bg=banner_bg,
        banner_icon=banner_label.split()[0],
        banner_label=banner_label,
        generated_date=generated_date,
        keyword=data.get("keyword", "未知关键词"),
        platform=platform_display,
        risk_color=risk_color,
        risk_label=risk_label,
        post_count=data.get("post_count", 1),
        core_issue=core_issue,
        report=report,
        link_count=len(data.get("urls", [])),
        link_items=_build_link_items(data.get("urls", [])),
        generated_time=generated_time,
    )
    return html


# ============================================================
# LLM 结构化数据生成
# ============================================================

LLM_JSON_PROMPT = """你是一个舆情分析数据提取专家。从以下舆情数据中提取关键信息，输出标准 JSON 对象。

输出格式（严格 JSON，禁止其他内容）：
{
  "core_issue": "核心问题简述（50字以内）",
  "report_summary": "预警简报摘要（100字以内，抓取最关键内容）",
  "risk_level": 风险等级数字 1-5,
  "risk_class": "low|medium|high|critical|neutral"
}

注意：
- core_issue 要简洁，直击问题本质
- report_summary 要提炼报告中最有价值的信息
- risk_level 和 risk_class 要根据报告内容判断，不要照抄原文的风险等级
- 只输出 JSON，不要有任何其他文字"""


async def _call_llm_async(prompt: str, text: str) -> Optional[str]:
    """异步调用 LLM，返回文本内容"""
    loop = asyncio.get_event_loop()
    try:
        from .llm_gateway import call_llm
        res = await loop.run_in_executor(
            None,
            lambda: call_llm(
                prompt=prompt,
                text=text,
                response_format="text",
                engine=DEFAULT_ENGINE,
            )
        )
        if res.success and res.data:
            return res.data
        else:
            logger.warning(f"[PushGen] LLM 调用失败: {res.error}")
            return None
    except Exception as e:
        logger.error(f"[PushGen] LLM 调用异常: {e}")
        return None


async def generate_push_data(
    keyword: str,
    platforms: str,
    risk_level: int,
    risk_class: str,
    core_issue: str,
    report: str,
    post_count: int,
    posts_summary: str,
    urls: list[str],
    topic_id: str = "",
) -> dict:
    """
    调用 LLM 提取结构化数据（JSON）。
    返回 dict，失败时返回空 dict。
    """
    input_text = f"""【监控关键词】{keyword}
【涉及平台】{platforms}
【帖子数量】{post_count} 条
【原始风险等级】{risk_level}
【核心问题】{core_issue}
【原始报告内容】
{report}
【帖子摘要示例】
{posts_summary}"""

    result = await _call_llm_async(LLM_JSON_PROMPT, input_text)

    if not result:
        logger.warning(f"[PushGen] LLM 生成结构化数据失败，topic_id={topic_id}")
        return {}

    # 解析 JSON
    try:
        # 清理 markdown 代码块
        text = result.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        logger.info(f"[PushGen] LLM 数据提取成功: {data.get('core_issue', '')}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"[PushGen] JSON 解析失败: {e}, raw={result[:200]}")
        return {}


# ============================================================
# 每日简报 HTML 模板（汇报 + 回顾风格，区别于预警模板）
# ============================================================

DAILY_SUMMARY_TEMPLATE = """
<!-- MediaRadar 每日舆情简报 -->
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="max-width:620px;margin:0 auto;font-family:'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;
              background:#e8ecf1;">
  <!-- 顶部深色标题栏 -->
  <tr>
    <td style="padding:0;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="padding:28px 32px 24px 32px;background:#0d1b2a;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="vertical-align:middle;padding-right:16px;">
                  <span style="display:inline-block;padding:4px 10px;background:rgba(255,255,255,0.12);
                               border-radius:4px;font-size:11px;font-weight:600;color:rgba(255,255,255,0.85);
                               letter-spacing:0.5px;border:1px solid rgba(255,255,255,0.18);">
                    📊 每日舆情简报
                  </span>
                </td>
                <td align="right" style="vertical-align:middle;">
                  <span style="font-size:11px;color:rgba(255,255,255,0.45);letter-spacing:0.5px;">{report_date}</span>
                </td>
              </tr>
              <tr>
                <td colspan="2" style="padding-top:16px;">
                  <p style="margin:0;font-size:20px;font-weight:700;color:#ffffff;line-height:1.3;letter-spacing:-0.2px;">
                    {keyword_count} 个关键词 · 共 {total_count} 条舆情
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- 主内容区 -->
  <tr>
    <td style="padding:0 20px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:#ffffff;border-radius:0 0 14px 14px;">

        <!-- 今日概览统计行 -->
        <tr>
          <td style="padding:24px 20px 0;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="border-collapse:separate;border-spacing:0 6px;">
              <tr>
                <td width="33%" style="background:#f4f7fb;padding:16px 12px 14px;border-radius:8px;text-align:center;">
                  <p style="margin:0 0 4px;font-size:10px;color:#8a9aaa;letter-spacing:0.8px;text-transform:uppercase;">今日新增</p>
                  <p style="margin:0;font-size:22px;font-weight:700;color:#0d1b2a;">{total_count}</p>
                  <p style="margin:0;font-size:10px;color:#8a9aaa;">条</p>
                </td>
                <td width="6"></td>
                <td width="33%" style="background:#f4f7fb;padding:16px 12px 14px;border-radius:8px;text-align:center;">
                  <p style="margin:0 0 4px;font-size:10px;color:#8a9aaa;letter-spacing:0.8px;text-transform:uppercase;">高危</p>
                  <p style="margin:0;font-size:22px;font-weight:700;color:#c0392b;">{high_count}</p>
                  <p style="margin:0;font-size:10px;color:#8a9aaa;">条</p>
                </td>
                <td width="6"></td>
                <td width="33%" style="background:#f4f7fb;padding:16px 12px 14px;border-radius:8px;text-align:center;">
                  <p style="margin:0 0 4px;font-size:10px;color:#8a9aaa;letter-spacing:0.8px;text-transform:uppercase;">涉及平台</p>
                  <p style="margin:0;font-size:22px;font-weight:700;color:#0d1b2a;">{platform_count}</p>
                  <p style="margin:0;font-size:10px;color:#8a9aaa;">个</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- 分隔线 -->
        <tr>
          <td style="padding:20px 20px 0;">
            <tr><td style="height:1px;background:#e4eaf2;"></td></tr>
          </td>
        </tr>

        <!-- 关键词分块列表 -->
        {keyword_blocks}

        <!-- AI 总结区块 -->
        <tr>
          <td style="padding:0 20px;">
            <details style="display:block;" open>
              <summary style="cursor:pointer;user-select:none;padding:16px 0 14px;
                               list-style:none;border-bottom:1px solid #e4eaf2;">
                <span style="font-size:12px;font-weight:600;color:#0d1b2a;letter-spacing:0.3px;">📋 AI 舆情总结</span>
                <span style="float:right;font-size:11px;color:#8a9aaa;">▼</span>
              </summary>
              <div style="padding:16px 0;background:#f0f5fb;border-radius:8px;margin-bottom:14px;">
                <p style="margin:0;font-size:14px;color:#2d3f52;line-height:2;white-space:pre-wrap;">{ai_summary}</p>
              </div>
            </details>
          </td>
        </tr>

      </table>
    </td>
  </tr>

  <!-- 底部 -->
  <tr>
    <td style="padding:20px 20px 28px;">
      <p style="margin:0;text-align:center;font-size:10px;color:#8a9aaa;letter-spacing:0.5px;">
        MediaRadar · 舆情监测系统 · {generated_time}
      </p>
    </td>
  </tr>
</table>
"""

DAILY_KEYWORD_BLOCK_TEMPLATE = """
        <!-- 关键词块 -->
        <tr>
          <td style="padding:0 20px;">
            <details style="display:block;" {block_open}>
              <summary style="cursor:pointer;user-select:none;padding:14px 0;
                               list-style:none;border-bottom:1px solid #e4eaf2;">
                <span style="font-size:12px;font-weight:600;color:#0d1b2a;letter-spacing:0.3px;">{keyword_label}</span>
                <span style="float:right;font-size:11px;color:#8a9aaa;">{risk_label}&nbsp;▼</span>
              </summary>
              <div style="padding:14px 0;background:#f4f7fb;border-radius:8px;margin-bottom:10px;">
                <p style="margin:0;font-size:13px;color:#2d3f52;line-height:1.9;padding:0 12px;">{issue_summary}</p>
                {link_section}
              </div>
            </details>
          </td>
        </tr>
"""

DAILY_LINK_ITEM_TEMPLATE = """
                <p style="margin:0 12px 6px;font-size:12px;line-height:1.5;">
                  <a href="{url}" style="color:#1a3a5c;text-decoration:none;">{platform_icon} {platform_name} · 查看原文 →</a>
                </p>
"""


def _build_daily_keyword_block(keyword: str, items: list, index: int) -> str:
    """构建单个关键词的区块"""
    if not items:
        return ""

    total = len(items)
    # 取最高风险等级作为块标签
    risk_map = {"critical": 5, "high": 4, "medium": 3, "low": 2, "neutral": 1}
    max_risk = max(items, key=lambda x: risk_map.get(x.get("risk_class", "neutral"), 0))
    risk_class = max_risk.get("risk_class", "neutral")

    risk_meta = {
        "critical": ("#c0392b", "🚨 极高"),
        "high": ("#c0392b", "🔴 高"),
        "medium": ("#2471a3", "🔵 中"),
        "low": ("#1e8449", "🟢 低"),
        "neutral": ("#566573", "⚪ 正常"),
    }
    risk_color, risk_label = risk_meta.get(risk_class, ("#566573", "⚪ 正常"))

    # 取第一条的核心问题作摘要
    first_item = items[0]
    issue_summary = first_item.get("core_issue", "") or first_item.get("report", "")[:120]
    if len(issue_summary) >= 120:
        issue_summary = issue_summary[:120] + "..."

    # 链接列表 - 从 topic_posts 查实际帖子 URL
    topic_id = first_item.get("topic_id", "")
    link_items = []
    if topic_id:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.url FROM topic_posts tp
                    JOIN ai_results p ON tp.post_id = p.post_id
                    WHERE tp.topic_id = ? AND tp.is_current = 1
                    LIMIT 5
                """, (topic_id,))
                post_rows = cursor.fetchall()
                for post_row in post_rows:
                    url = post_row[0] if post_row[0] else ""
                    if url:
                        p = first_item.get("platforms", [""])[0] if first_item.get("platforms") else ""
                        pname = PLATFORM_EMOJI_MAP.get(p, p)
                        link_items.append(DAILY_LINK_ITEM_TEMPLATE.format(
                            url=url, platform_icon="🔗", platform_name=pname))
        except Exception:
            pass
    link_html = "".join(link_items) if link_items else '<p style="margin:0 12px 6px;font-size:12px;color:#8a9aaa;">暂无帖子链接</p>'

    return DAILY_KEYWORD_BLOCK_TEMPLATE.format(
        keyword_label=f"#{index} {keyword} · {total} 条",
        risk_label=f'<span style="color:{risk_color};">{risk_label}</span>',
        issue_summary=issue_summary,
        link_section=link_html,
        block_open="open" if index == 1 else "",
    )


async def generate_daily_summary_html() -> str:
    """
    生成每日简报 HTML。
    查询今日入库的 ai_results，汇总后返回 HTML。
    无数据时返回空字符串。
    """
    try:
        from .db_manager import get_db_connection
    except Exception as e:
        logger.error(f"[PushGen] 无法导入 db_manager: {e}")
        return ""

    # 查询今日数据（从 topic_summary，取最新的话题聚合结果）
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_start = today + " 00:00:00"
    today_end = today + " 23:59:59"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT keyword, platforms, risk_level, risk_class,
                       core_issue, report, last_seen, topic_id, post_count
                FROM topic_summary
                WHERE last_seen >= ? AND last_seen <= ?
                ORDER BY risk_level DESC, last_seen DESC
            """, (today_start, today_end))
            rows = cursor.fetchall()
    except Exception as e:
        logger.error(f"[PushGen] 查询今日舆情失败: {e}")
        return ""

    if not rows:
        logger.info(f"[PushGen] 今日({today})无新舆情，跳过简报")
        return ""

    # 构建原始数据列表
    raw_items = []
    for row in rows:
        try:
            platforms_list = json.loads(row[1]) if row[1] else []
        except Exception:
            platforms_list = []
        raw_items.append({
            "keyword": row[0] or "未知",
            "platforms": platforms_list,
            "risk_level": row[2] or 3,
            "risk_class": row[3] or "neutral",
            "core_issue": row[4] or "",
            "report": row[5] or "",
            "last_seen": row[6] or "",
            "topic_id": row[7] or "",
            "post_count": row[8] or 0,
        })

    # 按关键词分组
    keyword_groups: dict[str, list] = {}
    for item in raw_items:
        kw = item["keyword"]
        if kw not in keyword_groups:
            keyword_groups[kw] = []
        keyword_groups[kw].append(item)

    # 统计
    total_count = sum(item.get("post_count", 1) for item in raw_items)
    high_count = sum(1 for i in raw_items if i.get("risk_class") in ("high", "critical"))
    platform_set = set()
    for i in raw_items:
        for p in i.get("platforms", []):
            platform_set.add(p)
    platform_count = len(platform_set)

    # 构建关键词区块
    keyword_blocks = ""
    for idx, (kw, items) in enumerate(keyword_groups.items(), 1):
        keyword_blocks += _build_daily_keyword_block(kw, items, idx)

    # 调用 LLM 生成 AI 总结
    ai_summary = await _generate_daily_summary_text(raw_items, keyword_groups)

    now = datetime.datetime.now()
    report_date = now.strftime("%Y-%m-%d")
    generated_time = now.strftime("%Y-%m-%d %H:%M")

    html = DAILY_SUMMARY_TEMPLATE.format(
        report_date=report_date,
        keyword_count=len(keyword_groups),
        total_count=total_count,
        high_count=high_count,
        platform_count=platform_count,
        keyword_blocks=keyword_blocks,
        ai_summary=ai_summary,
        generated_time=generated_time,
    )
    logger.info(f"[PushGen] 每日简报生成成功: {total_count}条舆情, {len(keyword_groups)}个关键词")
    return html


async def _generate_daily_summary_text(raw_items: list, keyword_groups: dict) -> str:
    """调用 LLM 生成今日舆情总结"""
    if not raw_items:
        return "今日暂无新舆情数据。"

    # 构建输入摘要
    lines = []
    for kw, items in keyword_groups.items():
        risk_classes = [i.get("risk_class", "neutral") for i in items]
        all_platforms = []
        for i in items:
            all_platforms.extend(i.get("platforms", []))
        platforms = list(set(all_platforms))
        p_names = [PLATFORM_MAP.get(p, p) for p in platforms]
        total_posts = sum(item.get("post_count", 1) for item in items)
        lines.append(f"【{kw}】风险等级: {', '.join(risk_classes)}，涉及平台: {', '.join(p_names)}，共 {total_posts} 条")

    input_text = "\n".join(lines[:10])  # 最多10个关键词

    prompt = f"""你是一个舆情监测报告分析师。请根据以下今日舆情数据，生成一段简洁的总结分析。

要求：
1. 总结今日整体舆情态势（50-100字）
2. 指出最需要关注的关键词和风险点
3. 用中性、专业的语气，避免夸大
4. 不要列出具体帖子链接

今日舆情数据：
{input_text}

请直接输出总结文字，不要 JSON，不要列表，只要一段话。"""

    result = await _call_llm_async(prompt, "")
    if not result:
        return "今日舆情态势平稳，暂无异常高危信息。"
    return result.strip()


# ============================================================
# 主入口：生成 HTML
# ============================================================

async def generate_push_html(
    keyword: str,
    platforms: str,
    risk_level: int,
    risk_class: str,
    core_issue: str,
    report: str,
    post_count: int,
    posts_summary: str,
    urls: list[str],
    topic_id: str = "",
) -> str:
    """
    生成精美 HTML 邮件内容。

    流程：LLM 提取结构化数据 → 填入固定模板 → 返回一致风格 HTML
    失败时返回空字符串。
    """
    # 1. LLM 提取结构化数据
    llm_data = await generate_push_data(
        keyword=keyword,
        platforms=platforms,
        risk_level=risk_level,
        risk_class=risk_class,
        core_issue=core_issue,
        report=report,
        post_count=post_count,
        posts_summary=posts_summary,
        urls=urls,
        topic_id=topic_id,
    )

    # 2. 构建最终渲染数据（LLM 数据优先级，但保留原始字段作兜底）
    render_data = {
        "keyword": keyword,
        "platform": platforms,
        "risk_level": risk_level,
        "risk_class": llm_data.get("risk_class", risk_class) if llm_data else risk_class,
        "core_issue": llm_data.get("core_issue", core_issue) if llm_data else core_issue,
        "report": llm_data.get("report_summary", report) if llm_data else report,
        "post_count": post_count,
        "urls": urls,
        "generated_at": datetime.datetime.now().isoformat(),
    }

    # 3. 固定模板渲染
    html = render_push_html(render_data)
    logger.info(f"[PushGen] HTML 生成成功，topic_id={topic_id}")
    return html
