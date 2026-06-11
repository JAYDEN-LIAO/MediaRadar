"""
RSS 推送通道（v2.2）

RSS 并非"推送"通道（不发消息），而是为每个用户生成唯一 RSS URL，
第三方阅读器（Feedly / Inoreader / Reeder）拉取话题更新。

实现：
  - generate_rss_xml(owner_id, token) → RSS 2.0 XML
  - RSS 端点 /rss/{token}.xml 在 api.py 中注册
"""
import datetime
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import get_logger

logger = get_logger("notifier.rss")

RSS_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>MediaRadar 话题订阅</title>
    <link>{base_url}/agent</link>
    <description>MediaRadar 媒体信息订阅平台 · 话题更新推送</description>
    <language>zh-CN</language>
    <lastBuildDate>{build_date}</lastBuildDate>
    <atom:link href="{rss_url}" rel="self" type="application/rss+xml"/>
    {items}
  </channel>
</rss>"""

RSS_ITEM_TEMPLATE = """
    <item>
      <title><![CDATA[{title}]]></title>
      <link>{link}</link>
      <description><![CDATA[{description}]]></description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{guid}</guid>
      <category>{keyword}</category>
      <content:encoded><![CDATA[{content_encoded}]]></content:encoded>
    </item>"""


def generate_rss_xml(
    owner_id: str,
    token: str,
    base_url: str = "https://mediaradar.jaydennn.xyz",
    limit: int = 20,
) -> str:
    """
    为指定用户生成 RSS 2.0 XML。

    查询该用户的最近活跃话题，按 last_seen 倒序排列。
    token 用于认证（URL 中的 token 需匹配 owner_id 的配置）。
    """
    try:
        from ..db_manager import get_topic_summary_list, get_topic_posts

        topics = get_topic_summary_list(
            owner_id=owner_id,
            is_admin=False,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"[RSS] 查询话题失败 owner={owner_id[:8]}...: {e}")
        topics = []

    rss_url = f"{base_url}/rss/{token}.xml"
    now = datetime.datetime.now(datetime.timezone.utc)
    build_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

    items_html = ""
    for t in topics:
        topic_id = t.get("topic_id", "")
        keyword = t.get("keyword", "")
        topic_name = t.get("topic_name", "未命名")
        summary = (t.get("cluster_summary") or t.get("report") or "")[:500]
        risk_level = t.get("risk_level", 0)
        post_count = t.get("post_count", 0)
        last_seen = t.get("last_seen", "")

        # 获取帖子 URL
        post_urls = []
        try:
            posts = get_topic_posts(topic_id, owner_id=owner_id, is_admin=False)
            for p in posts[:5]:
                if p.get("url"):
                    post_urls.append(p["url"])
        except Exception:
            pass

        # 发布日期格式
        try:
            dt = datetime.datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S")
            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        except (ValueError, TypeError):
            pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

        # HTML 内容
        risk_color = {4: "#c0392b", 3: "#2471a3", 2: "#1e8449"}.get(risk_level, "#566573")
        content_html = f"""
        <div style="font-family:sans-serif;padding:12px;background:#f8f9fa;border-radius:8px;">
          <div style="margin-bottom:8px;">
            <span style="color:{risk_color};font-weight:bold;font-size:14px;">风险 Lv.{risk_level}</span>
            <span style="margin-left:12px;color:#7f8c8d;font-size:12px;">{post_count} 条讨论</span>
          </div>
          <p style="font-size:13px;color:#333;line-height:1.6;">{summary}</p>
        </div>
        """

        if post_urls:
            content_html += "<ul style='margin-top:8px;padding-left:0;list-style:none;font-size:12px;'>"
            for u in post_urls[:5]:
                content_html += f'<li style="margin-bottom:4px;"><a href="{u}" style="color:#1a3a5c;">查看原文 →</a></li>'
            content_html += "</ul>"

        link = f"{base_url}/agent?topic={topic_id}"

        items_html += RSS_ITEM_TEMPLATE.format(
            title=topic_name,
            link=link,
            description=summary[:200],
            pub_date=pub_date,
            guid=f"{topic_id}-{last_seen[:10] if last_seen else '0'}",
            keyword=keyword,
            content_encoded=content_html,
        )

    if not topics:
        items_html = """
    <item>
      <title>欢迎使用 MediaRadar 话题订阅</title>
      <link>{base_url}</link>
      <description>暂无话题更新。当你关注的订阅产生新话题时，会在这里显示。</description>
      <pubDate>{build_date}</pubDate>
      <guid isPermaLink="false">welcome</guid>
    </item>
    """.format(base_url=base_url, build_date=build_date)

    return RSS_XML_TEMPLATE.format(
        base_url=base_url,
        rss_url=rss_url,
        build_date=build_date,
        items=items_html,
    )
