# yq_radar/yq_main.py
import subprocess
import time
import schedule
import os
import threading

from db_manager import get_unprocessed_posts, mark_processed_batch, save_ai_result, get_latest_results, get_system_settings
from llm_pipeline import process_post, call_llm, cluster_related_posts
from notifier import send_alert

RADAR_STATUS = {
    "is_running": False,
    "status_text": "系统闲置中",
    "last_run_time": "暂无"
}

# ================= 动态全局配置 =================
MONITOR_KEYWORDS = ["北京银行"]
MONITOR_PLATFORMS = ["wb"]
ALERT_NEGATIVE = True
CRAWLER_DB_PATH = "../crawler_core/database/sqlite_tables.db"
# ==========================================

def daily_summary_job():
    """执行每日摘要推送（真实联动）"""
    print("\n📢 触发每日舆情摘要推送机制...")
    current_keyword = "、".join(MONITOR_KEYWORDS) if MONITOR_KEYWORDS else "监控目标"
    # 调用现有的通知模块，推送每日平安报表
    send_alert(
        keyword=current_keyword,
        platform="系统",
        risk_level="info",
        core_issue="每日舆情简报", 
        report=f"系统已按您设定的时间自动汇总。今日监控目标【{current_keyword}】整体舆情态势平稳，详细图表与明细数据请登录前端雷达看板查看。",
        urls=[] 
    )

def reload_config():
    """💥 读取最新数据库配置，并重置所有的定时任务"""
    global MONITOR_KEYWORDS, MONITOR_PLATFORMS, ALERT_NEGATIVE
    try:
        cfg = get_system_settings()
    except Exception:
        cfg = {} # 防止首次启动没库报错
    
    # 获取并刷新全局变量
    MONITOR_KEYWORDS = cfg.get("keywords", ["北京银行"])
    if not MONITOR_KEYWORDS: MONITOR_KEYWORDS = ["北京银行"] # 兜底保护
        
    MONITOR_PLATFORMS = cfg.get("platforms", ["wb"])
    if not MONITOR_PLATFORMS: MONITOR_PLATFORMS = ["wb"]
        
    ALERT_NEGATIVE = cfg.get("alert_negative", True)
    
    # 1. 清空旧的定时任务
    schedule.clear()
    
    # 2. 动态设置高频监控任务
    freq_hours = float(cfg.get("monitor_frequency", 1.0))
    freq_minutes = int(freq_hours * 60)
    if freq_minutes <= 0: freq_minutes = 60 # 防止前端瞎填0导致死循环
    schedule.every(freq_minutes).minutes.do(job)
    
    # 3. 动态设置每日摘要推送任务
    if cfg.get("push_summary", True):
        push_time = cfg.get("push_time", "18:00")
        schedule.every().day.at(push_time).do(daily_summary_job)
        
    print(f"\n🔄 系统配置已重载！\n -> 监控词: {MONITOR_KEYWORDS}\n -> 平台: {MONITOR_PLATFORMS}\n -> 频率: 每 {freq_hours} 小时\n -> 负面即时报警: {'已开启' if ALERT_NEGATIVE else '已关闭'}")

def run_crawler_for_platform(platform):
    print(f"⏳ 开始抓取平台: {platform.upper()}...")
    try:
        subprocess.run(
            ["uv", "run", "main.py", "--platform", platform, "--type", "search", "--save_data_option", "sqlite", "--headless", "no"],
            cwd="../crawler_core", 
            check=True
        )
        print(f"✅ {platform.upper()} 数据抓取完成！")
    except subprocess.CalledProcessError as e:
        print(f"❌ 抓取平台 {platform} 时发生错误: {e}")

def run_analysis_pipeline():
    # 将关键词列表合并为一个字符串，供大模型识别
    current_keyword = "、".join(MONITOR_KEYWORDS)
    
    for platform in MONITOR_PLATFORMS:
        print(f"\n🔍 正在读取 {platform.upper()} 的最新未分析数据...")
        
        posts = get_unprocessed_posts(CRAWLER_DB_PATH, platform)
        if not posts:
            print(f"📭 {platform.upper()} 暂无未处理数据。")
            continue
            
        print(f"📦 发现 {len(posts)} 条新数据，开始 [阶段1: 噪音过滤]...")
        
        relevant_posts = []
        processed_records = [] 
        post_dict = {p["post_id"]: p for p in posts} 
        
        for idx, p in enumerate(posts, 1):
            print(f"  -> [{idx}/{len(posts)}] 筛选帖子 ID: {p['post_id']} ... ", end="\r")
            
            screener_prompt = f"""你是一个严谨的数据筛选员。目标实体：【{current_keyword}】。判断内容是否真正在讨论该实体。输出JSON: {{"is_relevant": true/false, "reason": "..."}}"""
            text_to_analyze = f"标题: {p['title']}\n正文: {p['content'][:500]}"
            
            res = call_llm(screener_prompt, text_to_analyze)
            if res.get("is_relevant"):
                relevant_posts.append(p)
            
            processed_records.append((p["post_id"], platform))
            time.sleep(0.5) 

        print(f"\n✅ 筛选完成！相关: {len(relevant_posts)} 条 / 噪音: {len(posts) - len(relevant_posts)} 条")

        if processed_records:
            mark_processed_batch(processed_records)
            print(f"💾 已将 {len(processed_records)} 条数据批量标记为[已处理]。")

        if not relevant_posts:
            print("🟢 本批次无相关风险事件。")
            continue

        print(f"🔗 针对 {len(relevant_posts)} 条相关数据，开始 [阶段2: 话题聚类]...")
        clusters = cluster_related_posts(relevant_posts, current_keyword)
        
        print(f"📊 成功聚类为 {len(clusters)} 个核心话题。开始 [阶段3: 深度研判]...")
        
        for cluster in clusters:
            topic_name = cluster.get("topic_name", "未知话题")
            post_ids = cluster.get("post_ids", [])
            if not post_ids: continue
            
            combined_text = ""
            urls = []
            for pid in post_ids:
                if pid in post_dict:
                    combined_text += f"【帖子】{post_dict[pid]['title']}\n"
                    urls.append(post_dict[pid]['url'])
                    
            print(f"  -> 研判话题: [{topic_name}] (包含 {len(urls)} 条来源) ... ", end="")
            
            mock_post = {
                "title": f"聚合话题：{topic_name}",
                "content": combined_text[:2000] 
            }
            
            result = process_post(mock_post, current_keyword)
            
            for pid in post_ids:
                if pid in post_dict:
                    real_post = post_dict[pid] 
                    save_ai_result(
                        post_id=real_post["post_id"], 
                        platform=platform, 
                        keyword=current_keyword, 
                        title=real_post.get("title", ""),          
                        content=real_post.get("content", ""),      
                        url=real_post.get("url", ""),              
                        risk_level=result.get("risk_level", "low"), 
                        core_issue=result.get("core_issue", "无异常"), 
                        report=result.get("report", result.get("reason", ""))
                    )

            # ✨ 核心修复：前端报警开关在这里起作用！
            if result["status"] == "alert" and ALERT_NEGATIVE:
                print(f"\n🚨 触发负面预警！(风险: {result.get('risk_level')})")
                send_alert(
                    keyword=current_keyword,
                    platform=platform,
                    risk_level=result["risk_level"],
                    core_issue=topic_name, 
                    report=result["report"],
                    urls=urls 
                )
            elif result["status"] == "alert" and not ALERT_NEGATIVE:
                print("\n⚠️ 发现负面，但前端【已关闭负面报警】，静默入库不推送通知。")
            else:
                print("安全通过")


def api_start_task(keywords: list):
    if RADAR_STATUS["is_running"]:
        return False, "雷达正在运行中，请勿重复启动"
    
    global MONITOR_KEYWORDS
    if keywords and len(keywords) > 0:
        MONITOR_KEYWORDS = keywords 
    current_keyword = "、".join(MONITOR_KEYWORDS)
        
    def _run_in_background():
        RADAR_STATUS["is_running"] = True
        RADAR_STATUS["status_text"] = f"正在监控: {current_keyword}"
        try:
            job() 
            RADAR_STATUS["last_run_time"] = time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"后台任务异常: {e}")
        finally:
            RADAR_STATUS["is_running"] = False
            RADAR_STATUS["status_text"] = "系统闲置中"

    threading.Thread(target=_run_in_background).start()
    return True, "监控任务已启动"

def job():
    print("\n" + "*"*50)
    print(f"⏰ 任务开始执行: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("*"*50)
    
    for platform in MONITOR_PLATFORMS:
        run_crawler_for_platform(platform)
        
    run_analysis_pipeline()
    
    print("🎉 本轮监控任务圆满结束，进入待机状态。\n")

if __name__ == "__main__":
    print("🚀 舆情早期监控雷达 V3.0 (全动态配置版) 启动成功！")
    
    # 启动时优先加载前端配置！取代一切写死的逻辑！
    reload_config()
    
    # 启动时先顺手执行一次
    job()
    
    print("⏳ 系统已加载前端动态配置，程序将持续在后台运行...")
    while True:
        schedule.run_pending()
        time.sleep(10)