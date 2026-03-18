# yq_radar/notifier.py
import requests
import json

# ================= 配置区 =================
# 方案 A: Server酱 (微信推送)，极其简单，去 sct.ftqq.com 免费领一个 SendKey
SERVERCHAN_SENDKEY = "" 

# 方案 B: 钉钉群机器人 Webhook (推荐企业使用)
DINGTALK_WEBHOOK = "" 
# ==========================================

def send_via_serverchan(title, content):
    if not SERVERCHAN_SENDKEY:
        return
    url = f"[https://sctapi.ftqq.com/](https://sctapi.ftqq.com/){SERVERCHAN_SENDKEY}.send"
    data = {
        "title": title,
        "desp": content
    }
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Server酱发送失败: {e}")

def send_via_dingtalk(title, content):
    if not DINGTALK_WEBHOOK:
        return
    headers = {'Content-Type': 'application/json'}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"### {title}\n\n{content}"
        }
    }
    try:
        requests.post(DINGTALK_WEBHOOK, headers=headers, data=json.dumps(data), timeout=10)
    except Exception as e:
        print(f"⚠️ 钉钉发送失败: {e}")

def send_alert(keyword, platform, risk_level, core_issue, report, urls):
    """统一的预警发送接口（支持聚合多链接）"""
    
    # 组装链接列表的 Markdown 文本
    links_md = "\n".join([f"- [来源链接 {i+1}]({url})" for i, url in enumerate(urls)])
    
    title = f"🚨【舆情预警】{keyword} 出现风险事件"
    content = f"""
**监测平台**：{platform.upper()}
**风险等级**：{risk_level} 级 (满分5级)
**话题概括**：{core_issue}
**受波及贴数**：{len(urls)} 条

**预警简报**：
{report}

**溯源链接**：
{links_md}
    """
    
    print("\n" + "="*40)
    print(title)
    print(content)
    print("="*40 + "\n")

    send_via_serverchan(title, content)
    send_via_dingtalk(title, content)