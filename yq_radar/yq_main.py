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
MONITOR_KEYWORDS = []
MONITOR_PLATFORMS = []
ALERT_NEGATIVE = True
CRAWLER_DB_PATH = "../crawler_core/database/sqlite_tables.db"
# ==========================================

def daily_summary_job():
    print("\n📢 触发每日舆情摘要推送机制...")
    current_keyword = "、".join(MONITOR_KEYWORDS) if MONITOR_KEYWORDS else "监控目标"
    send_alert(
        keyword=current_keyword,
        platform="系统",
        risk_level="info",
        core_issue="每日舆情简报", 
        report=f"系统已按设定的时间自动汇总。今日监控目标【{current_keyword}】舆情态势平稳，详细数据请登录前端看板查看。",
        urls=[] 
    )

def reload_config():
    """💥 读取最新数据库配置，并重置所有的定时任务"""
    global MONITOR_KEYWORDS, MONITOR_PLATFORMS, ALERT_NEGATIVE
    try:
        cfg = get_system_settings()
    except Exception:
        cfg = {} 
    
    MONITOR_KEYWORDS = cfg.get("keywords", ["北京银行"])
    if not MONITOR_KEYWORDS: MONITOR_KEYWORDS = ["北京银行"] 
        
    MONITOR_PLATFORMS = cfg.get("platforms", ["wb"])
    if not MONITOR_PLATFORMS: MONITOR_PLATFORMS = ["wb"]
        
    ALERT_NEGATIVE = cfg.get("alert_negative", True)
    
    schedule.clear()
    
    freq_hours = float(cfg.get("monitor_frequency", 1.0))
    freq_minutes = int(freq_hours * 60)
    if freq_minutes <= 0: freq_minutes = 60 
    schedule.every(freq_minutes).minutes.do(job)
    
    if cfg.get("push_summary", True):
        push_time = cfg.get("push_time", "18:00")
        schedule.every().day.at(push_time).do(daily_summary_job)
        
    print(f"\n🔄 系统配置已重载！\n -> 监控词: {MONITOR_KEYWORDS}\n -> 平台: {MONITOR_PLATFORMS}\n -> 频率: 每 {freq_hours} 小时")

def run_crawler_for_platform(platform):
    """单平台抓取函数（串行模式，带环境变量隔离）"""
    print(f"\n⏳ 开始抓取平台: {platform.upper()}...")
    try:
        # 剔除父进程虚拟环境
        clean_env = os.environ.copy()
        if "VIRTUAL_ENV" in clean_env:
            del clean_env["VIRTUAL_ENV"]
            
        # ✨ 核心修复：把系统最新的监控词转换成逗号分隔的字符串
        if not MONITOR_KEYWORDS:
            print("⚠️ 警告：当前没有设置任何监控词，跳过抓取！")
            return
            
        keywords_str = ",".join(MONITOR_KEYWORDS)
        print(f"🎯 正在向爬虫强行下发搜索指令，目标关键词: 【{keywords_str}】")
            
        subprocess.run(
            [
                "uv", "run", "main.py", 
                "--platform", platform, 
                "--type", "search", 
                "--save_data_option", "sqlite", 
                "--headless", "no",
                "--keywords", keywords_str  # <--- 就是这行！强行覆盖底层爬虫的硬编码！
            ],
            cwd="../crawler_core", 
            env=clean_env, 
            check=True
        )
        print(f"✅ {platform.upper()} 数据抓取完毕！")
    except subprocess.CalledProcessError as e:
        print(f"❌ 抓取平台 {platform} 时发生错误: {e}")

def run_analysis_pipeline():
    for platform in MONITOR_PLATFORMS:
        print(f"\n🔍 正在读取 {platform.upper()} 的最新未分析数据...")
        posts = get_unprocessed_posts(CRAWLER_DB_PATH, platform)
        if not posts:
            print(f"📭 {platform.upper()} 暂无未处理数据。")
            continue
            
        print(f"📦 发现 {len(posts)} 条新数据，开始 [阶段1: 噪音过滤与分拣]...")
        relevant_posts = []
        processed_records = [] 
        post_dict = {p["post_id"]: p for p in posts} 
        
        for idx, p in enumerate(posts, 1):
            print(f"  -> [{idx}/{len(posts)}] 筛选帖子 ID: {p['post_id']} ... ", end="\r")
            
            # ✨ 核心改动 1：要求大模型明确指出匹配到了哪个具体的关键词
            screener_prompt = f"""你是一个严谨的数据筛选员。请判断以下内容是否真正在讨论这些目标实体之一：{MONITOR_KEYWORDS}。
输出严格的JSON格式: {{"is_relevant": true/false, "matched_keyword": "这里填匹配到的具体实体(必须从前面的列表中原样抄写, 如无则留空)", "reason": "..."}}"""
            
            text_to_analyze = f"标题: {p['title']}\n正文: {p['content'][:500]}"
            res = call_llm(screener_prompt, text_to_analyze)
            
            if res.get("is_relevant"):
                # 提取大模型识别出的具体实体
                matched_kw = res.get("matched_keyword")
                # 兜底校验：如果大模型胡言乱语或者没填，用字符串包含法强行纠正
                if not matched_kw or matched_kw not in MONITOR_KEYWORDS:
                    matched_kw = next((k for k in MONITOR_KEYWORDS if k in text_to_analyze), MONITOR_KEYWORDS[0])
                
                p["matched_keyword"] = matched_kw
                relevant_posts.append(p)
                
            processed_records.append((p["post_id"], platform))
            time.sleep(0.5) 

        print(f"\n✅ 筛选完成！相关: {len(relevant_posts)} 条 / 噪音: {len(posts) - len(relevant_posts)} 条")

        if processed_records:
            mark_processed_batch(processed_records)
            print(f"💾 已将 {len(processed_records)} 条数据批量标记为[已处理]。")

        if not relevant_posts:
            continue

        # ✨ 核心改动 2：将筛选后的帖子按具体的“关键词”分组！
        # 这样黄仁勋的帖子就不会和北京银行的帖子搞混在一起研判了
        grouped_posts = {}
        for p in relevant_posts:
            kw = p["matched_keyword"]
            if kw not in grouped_posts:
                grouped_posts[kw] = []
            grouped_posts[kw].append(p)

        # ✨ 核心改动 3：针对每个不同的关键词，独立进行聚类、分析和入库
        for specific_keyword, group_posts in grouped_posts.items():
            print(f"\n🔗 针对【{specific_keyword}】的 {len(group_posts)} 条数据，开始 [阶段2: 话题聚类]...")
            clusters = cluster_related_posts(group_posts, specific_keyword)
            
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
                
                mock_post = { "title": f"聚合话题：{topic_name}", "content": combined_text[:2000] }
                result = process_post(mock_post, specific_keyword)
                
                for pid in post_ids:
                    if pid in post_dict:
                        real_post = post_dict[pid] 
                        save_ai_result(
                            post_id=real_post["post_id"], platform=platform, 
                            keyword=specific_keyword,  # 🎯 核心成果：存入数据库的终于是一个干净的词了！
                            title=real_post.get("title", ""), content=real_post.get("content", ""), url=real_post.get("url", ""),              
                            risk_level=result.get("risk_level", "low"), core_issue=result.get("core_issue", "无异常"), report=result.get("report", result.get("reason", ""))
                        )

                if result["status"] == "alert" and ALERT_NEGATIVE:
                    print(f"\n🚨 触发负面预警！(风险: {result.get('risk_level')})")
                    send_alert(
                        keyword=specific_keyword, platform=platform, risk_level=result["risk_level"],
                        core_issue=topic_name, report=result["report"], urls=urls 
                    )
                elif result["status"] == "alert" and not ALERT_NEGATIVE:
                    print("\n⚠️ 发现负面，但前端【已关闭负面报警】，静默入库不推送通知。")
                else:
                    print("安全通过")


def api_start_task():
    if RADAR_STATUS["is_running"]:
        return False, "雷达正在运行中，请勿重复启动"
    
    reload_config()
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
    return True, "扫描任务已启动"

def job():
    print("\n" + "="*60)
    print(f"🚀 平台队列扫描任务开始: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # ✨ 核心改造：使用安全的串行排队抓取，告别端口冲突！
    if MONITOR_PLATFORMS:
        print(f"⚡ 共需抓取 {len(MONITOR_PLATFORMS)} 个平台，进入稳定排队抓取模式...")
        for platform in MONITOR_PLATFORMS:
            run_crawler_for_platform(platform)
            # 休息 3 秒，让底层的无头浏览器进程彻底释放 9222 端口，防止下一个平台启动失败
            time.sleep(3)
    
    print("\n🏁 所有平台抓取完毕，开始进入 AI 统一研判流水线...")
    run_analysis_pipeline()
    
    print("🎉 本轮扫描任务圆满结束，进入待机状态。\n")

if __name__ == "__main__":
    print("🚀 舆情早期监控雷达 V5.0 (极稳排队版) 启动成功！")
    reload_config()
    job()
    print("⏳ 系统已加载前端动态配置，程序将持续在后台运行...")
    while True:
        schedule.run_pending()
        time.sleep(10)