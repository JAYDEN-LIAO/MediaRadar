# backend/services/radar_service/yq_main.py
import subprocess
import time
import schedule
import os
import sys
import threading


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

BACKEND_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))

PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

CRAWLER_DIR = os.path.join(BACKEND_DIR, "services", "crawler_service")


from core.logger import logger
from core.config import settings
from .db_manager import get_unprocessed_posts, mark_processed_batch, save_ai_result, get_system_settings
from .llm_pipeline import process_post, call_llm, cluster_related_posts
from .notifier import send_alert

RADAR_STATUS = {
    "is_running": False,
    "status_text": "系统闲置中",
    "last_run_time": "暂无"
}

MONITOR_KEYWORDS = []
MONITOR_PLATFORMS = []
ALERT_NEGATIVE = True

def daily_summary_job():
    logger.info("Triggering daily summary notification.")
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
        
    logger.info(f"Configuration reloaded. Keywords: {MONITOR_KEYWORDS}, Platforms: {MONITOR_PLATFORMS}, Freq: {freq_hours}h")

def run_crawler_for_platform(platform):
    logger.info(f"Starting crawler for platform: {platform.upper()}")
    try:
        clean_env = os.environ.copy()
        if "VIRTUAL_ENV" in clean_env:
            del clean_env["VIRTUAL_ENV"]
            
        if not MONITOR_KEYWORDS:
            logger.warning("No keywords specified, skipping task.")
            return
            
        keywords_str = ",".join(MONITOR_KEYWORDS)
        logger.info(f"Executing task with keywords: {keywords_str}")
        
        logger.info(f"【路径探针】程序计算出的爬虫根目录为: {CRAWLER_DIR}")
        if not os.path.exists(CRAWLER_DIR):
            logger.error(f"【致命错误】找不到该目录！请检查你的真实爬虫文件夹叫什么名字！")
            return

        subprocess.run(
            [
                "uv", "run", "main.py", 
                "--platform", platform, 
                "--type", "search", 
                "--save_data_option", "sqlite", 
                "--headless", "no",
                "--keywords", keywords_str
            ],
            cwd=CRAWLER_DIR, 
            env=clean_env, 
            check=True,
            timeout=600 
        )
        logger.info(f"{platform.upper()} data extraction completed.")
    except subprocess.TimeoutExpired:
        logger.error(f"Task timeout for platform {platform}, terminated forcefully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Execution failed for platform {platform}: {e}")

def run_analysis_pipeline():
    for platform in MONITOR_PLATFORMS:
        logger.info(f"Analyzing unprocessed data for {platform.upper()}...")
        posts = get_unprocessed_posts(settings.CRAWLER_DB_PATH, platform)
        if not posts:
            continue
            
        relevant_posts = []
        processed_records = [] 
        post_dict = {p["post_id"]: p for p in posts} 
        
        for idx, p in enumerate(posts, 1):
            screener_prompt = f"""你是一个严谨的数据筛选员。请判断以下内容是否讨论目标实体之一：{MONITOR_KEYWORDS}。
输出JSON格式: {{"is_relevant": true/false, "matched_keyword": "匹配的具体实体名", "reason": "..."}}"""
            
            text_to_analyze = f"标题: {p['title']}\n正文: {p['content'][:500]}"
            res = call_llm(screener_prompt, text_to_analyze)
            
            if res.get("is_relevant"):
                matched_kw = res.get("matched_keyword")
                if not matched_kw or matched_kw not in MONITOR_KEYWORDS:
                    matched_kw = next((k for k in MONITOR_KEYWORDS if k in text_to_analyze), MONITOR_KEYWORDS[0])
                
                p["matched_keyword"] = matched_kw
                relevant_posts.append(p)
                
            processed_records.append((p["post_id"], platform))
            #time.sleep(0.5) 

        logger.info(f"Filter completed. Relevant: {len(relevant_posts)} | Irrelevant: {len(posts) - len(relevant_posts)}")

        if processed_records:
            mark_processed_batch(processed_records)

        if not relevant_posts:
            continue

        grouped_posts = {}
        for p in relevant_posts:
            kw = p["matched_keyword"]
            if kw not in grouped_posts:
                grouped_posts[kw] = []
            grouped_posts[kw].append(p)

        for specific_keyword, group_posts in grouped_posts.items():
            logger.info(f"Clustering {len(group_posts)} records for keyword: {specific_keyword}")
            clusters = cluster_related_posts(group_posts, specific_keyword)
            
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
                        
                mock_post = { "title": f"聚合话题：{topic_name}", "content": combined_text[:2000] }
                result = process_post(mock_post, specific_keyword)
                
                for pid in post_ids:
                    if pid in post_dict:
                        real_post = post_dict[pid] 
                        save_ai_result(
                            post_id=real_post["post_id"], platform=platform, 
                            keyword=specific_keyword, 
                            title=real_post.get("title", ""), content=real_post.get("content", ""), url=real_post.get("url", ""),              
                            risk_level=result.get("risk_level", "low"), core_issue=result.get("core_issue", "无异常"), report=result.get("report", result.get("reason", ""))
                        )

                if result["status"] == "alert" and ALERT_NEGATIVE:
                    logger.warning(f"Negative sentiment detected. Risk level: {result.get('risk_level')}")
                    send_alert(
                        keyword=specific_keyword, platform=platform, risk_level=result["risk_level"],
                        core_issue=topic_name, report=result["report"], urls=urls 
                    )
                else:
                    logger.info(f"Status check passed for topic: {topic_name}")

def api_start_task():
    if RADAR_STATUS["is_running"]:
        return False, "扫描任务正在运行中，请勿重复启动"
    
    reload_config()
    current_keyword = "、".join(MONITOR_KEYWORDS)
        
    def _run_in_background():
        RADAR_STATUS["is_running"] = True
        RADAR_STATUS["status_text"] = f"正在监控: {current_keyword}"
        try:
            job() 
            RADAR_STATUS["last_run_time"] = time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.error(f"Background task exception: {e}")
        finally:
            RADAR_STATUS["is_running"] = False
            RADAR_STATUS["status_text"] = "系统闲置中"

    threading.Thread(target=_run_in_background).start()
    return True, "扫描任务已启动"

def job():
    logger.info("Starting radar job pipeline")
    if MONITOR_PLATFORMS:
        for platform in MONITOR_PLATFORMS:
            run_crawler_for_platform(platform)
            time.sleep(3)
    
    run_analysis_pipeline()
    logger.info("Pipeline execution finished.")

if __name__ == "__main__":
    logger.info("YQ Radar Engine Initialized.")
    reload_config()
    job()
    while True:
        schedule.run_pending()
        time.sleep(10)