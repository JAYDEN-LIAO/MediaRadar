# backend/services/radar_service/main.py
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
from .llm_pipeline import analyze_and_report, call_llm, cluster_related_posts, call_vision_llm, ScreenerResult
from .prompt_templates import SCREENER_PROMPT
from .notifier import send_alert

RADAR_STATUS = {
    "is_running": False, 
    "status_text": "系统闲置中", 
    "last_run_time": "暂无",
    "last_new_count": 0
}
MONITOR_KEYWORDS = []
MONITOR_PLATFORMS = []
ALERT_NEGATIVE = True
MONITOR_KEYWORD_LEVELS = {}

def daily_summary_job():
    logger.info("Triggering daily summary notification.")
    current_keyword = "、".join(MONITOR_KEYWORDS) if MONITOR_KEYWORDS else "监控目标"
    send_alert(
        keyword=current_keyword, platform="全部平台", risk_level="info",
        core_issue="每日舆情监测总结", report="今日监测已完成，详情请登录后台查看。", urls=[]
    )

def reload_config():
    global MONITOR_KEYWORDS, MONITOR_KEYWORD_LEVELS, MONITOR_PLATFORMS, ALERT_NEGATIVE
    try:
        conf = get_system_settings()
    except Exception:
        conf = {} 
        
    MONITOR_KEYWORDS = []
    MONITOR_KEYWORD_LEVELS = {}
    
    for kw in conf.get("keywords", []):
        if isinstance(kw, str):
            MONITOR_KEYWORDS.append(kw)
            MONITOR_KEYWORD_LEVELS[kw] = "balanced"
        elif isinstance(kw, dict):
            text = kw.get("text")
            if text:
                MONITOR_KEYWORDS.append(text)
                MONITOR_KEYWORD_LEVELS[text] = kw.get("level", "balanced")
                
    MONITOR_PLATFORMS = conf.get("platforms", [])
    ALERT_NEGATIVE = conf.get("alert_negative", True)
    logger.info(f"Loaded config: keywords={MONITOR_KEYWORDS}, levels={MONITOR_KEYWORD_LEVELS}")

def run_crawler_for_platform(platform):
    logger.info(f"Starting crawler for platform: {platform.upper()}")
    try:
        # clean_env = os.environ.copy()
        # if "VIRTUAL_ENV" in clean_env:
        #     del clean_env["VIRTUAL_ENV"]
            
        if not MONITOR_KEYWORDS:
            logger.warning("No keywords specified, skipping task.")
            return
            
        keywords_str = ",".join(MONITOR_KEYWORDS)
        logger.info(f"Executing task with keywords: {keywords_str}")
        
        if not os.path.exists(CRAWLER_DIR):
            logger.error(f"【致命错误】找不到爬虫目录: {CRAWLER_DIR}")
            return

        subprocess.run(
            [
                sys.executable, "main.py", 
                "--platform", platform, 
                "--type", "search", 
                "--save_data_option", "sqlite", 
                "--headless", "no",
                "--keywords", keywords_str
            ],
            cwd=CRAWLER_DIR, 
            # env=clean_env, 
            check=True,
            timeout=600 
        )
        logger.info(f"{platform.upper()} data extraction completed.")
    except subprocess.TimeoutExpired:
        logger.error(f"Task timeout for platform {platform}, terminated forcefully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Execution failed for platform {platform}: {e}")

def run_analysis_pipeline():
    total_new_count = 0

    for platform in MONITOR_PLATFORMS:
        logger.info(f"Analyzing unprocessed data for {platform.upper()}...")
        posts = get_unprocessed_posts(settings.CRAWLER_DB_PATH, platform)
        if not posts:
            continue
            
        relevant_posts = []
        processed_records = [] 
        post_dict = {p["post_id"]: p for p in posts} 
        
        # backend/services/radar_service/main.py (替换 run_analysis_pipeline 内部循环)

        for idx, p in enumerate(posts, 1):
            text_content = p.get('content', '')
            image_urls = p.get('image_urls', [])
            has_image = bool(image_urls)
            
            logger.info(f"正在使用 Screener 初筛数据: {idx}/{len(posts)} (PostID: {p['post_id']})")
            
            kw_with_levels = "、".join([f"{k}(监控等级:{MONITOR_KEYWORD_LEVELS.get(k, 'balanced')})" for k in MONITOR_KEYWORDS])
            screener_prompt = SCREENER_PROMPT.format(keyword=kw_with_levels)
            
            # 💡 妙招：用系统提示告诉大模型这里有图，让它自己决定要不要看
            image_hint = "\n【系统提示】：该帖子附带了图片，如果文本存疑或需要证据，可申请看图。" if has_image else ""
            text_to_analyze = f"标题: {p['title']}\n正文: {text_content[:800]}{image_hint}"
            
            # 【第一道关卡：纯文本初筛】
            res = call_llm(
                screener_prompt, text_to_analyze, 
                response_format="json", engine="deepseek", pydantic_model=ScreenerResult
            )
            
            # 如果判定无关，且不申请看图（例如纯广告、日常打卡），直接早退 (Early Exit)！
            if not res.get("is_relevant") and not res.get("needs_vision"):
                logger.info(f"⏭️ [早退] 文本判定为无关噪音，无需看图，直接跳过 (ID:{p['post_id']})")
                processed_records.append((p["post_id"], platform))
                continue
            
            # 如果大模型申请看图，且确实有图，则调用 Vision Agent
            if res.get("needs_vision") and has_image:
                logger.info(f"📸 [级联触发] Screener 申请看图 (ID:{p['post_id']})，呼叫 Vision Agent 解析...")
                vision_text = call_vision_llm(image_urls[0], text_content, platform=platform, post_id=p.get('post_id'))
                
                if vision_text:
                    # 将视觉特征拼接到正文
                    text_content = f"{text_content}\n【视觉补充】：{vision_text}"
                    text_to_analyze = f"标题: {p['title']}\n正文: {text_content[:800]}"
                    
                    logger.info("🔄 [二次确认] 图文融合完毕，交回 Screener 做最终判定...")
                    # 【第二道关卡：图文综合复判】
                    res = call_llm(
                        screener_prompt, text_to_analyze, 
                        response_format="json", engine="deepseek", pydantic_model=ScreenerResult
                    )

            # 经过重重关卡，最终判定为相关的，才放入队列
            if res.get("is_relevant"):
                matched_kw = res.get("matched_keyword")
                if not matched_kw or matched_kw not in MONITOR_KEYWORDS:
                    matched_kw = next((k for k in MONITOR_KEYWORDS if k in text_to_analyze), MONITOR_KEYWORDS[0])
                
                p["content"] = text_content
                p["matched_keyword"] = matched_kw
                relevant_posts.append(p)
                logger.info(f"✅ [通过] 成功捕获有效舆情: {p['title'][:15]}...")
                
            processed_records.append((p["post_id"], platform))

        logger.info(f"初筛漏斗完成. 相关入库: {len(relevant_posts)} | 过滤无关: {len(posts) - len(relevant_posts)}")

        if processed_records:
            mark_processed_batch(processed_records)

        if not relevant_posts:
            continue

        grouped_posts = {}
        for p in relevant_posts:
            kw = p["matched_keyword"]
            grouped_posts.setdefault(kw, []).append(p)

        for specific_keyword, group_posts in grouped_posts.items():
            logger.info(f"正在对关键字 [{specific_keyword}] 的 {len(group_posts)} 条数据进行聚类...")
            clusters = cluster_related_posts(group_posts, specific_keyword)
            
            for cluster in clusters:
                topic_name = cluster.get("topic_name", "未知话题")
                post_ids = cluster.get("post_ids", [])
                if not post_ids: continue
                
                logger.info(f"📊 [聚类结果明细] 提取到话题: 【{topic_name}】 -> 包含 {len(post_ids)} 条讨论帖子")

                combined_text = ""
                urls = []
                for pid in post_ids:
                    if pid in post_dict:
                        combined_text += f"【发帖】{post_dict[pid]['title']} - {post_dict[pid].get('content', '')[:200]}\n"
                        urls.append(post_dict[pid].get('url', ''))
                        
                mock_post = { "title": f"聚合话题：{topic_name}", "content": combined_text[:2500] }
                
                current_sensitivity = MONITOR_KEYWORD_LEVELS.get(specific_keyword, "balanced")
                result = analyze_and_report(mock_post, specific_keyword, sensitivity=current_sensitivity)
                
                for pid in post_ids:
                    if pid in post_dict:
                        real_post = post_dict[pid] 
                        save_ai_result(
                            post_id=pid, 
                            platform=platform,
                            keyword=specific_keyword, 
                            title=real_post.get("title", ""), 
                            content=real_post.get("content", ""),
                            url=real_post.get("url", ""),
                            risk_level=result["risk_level"],
                            core_issue=result["core_issue"],
                            report=result["report"],
                            publish_time=real_post.get("publish_time", "未知时间") 
                        )
                        total_new_count += 1 

                if result.get("status") == "alert" and ALERT_NEGATIVE:
                    logger.warning(f"🚨 高危预警产生！等级: {result.get('risk_level')}")
                    send_alert(
                        keyword=specific_keyword, platform=platform, risk_level=result["risk_level"],
                        core_issue=topic_name, report=result["report"], urls=urls 
                    )
                else:
                    logger.info(f"✅ 话题检测安全通过: {topic_name}")

    return total_new_count


def api_start_task(background_tasks):
    if RADAR_STATUS["is_running"]:
        return False, "扫描任务正在运行中，请勿重复启动"
    
    reload_config()
    current_keyword = "、".join(MONITOR_KEYWORDS)
        
    def _run_in_background():
        RADAR_STATUS["is_running"] = True
        RADAR_STATUS["status_text"] = f"正在监控: {current_keyword}"
        RADAR_STATUS["last_new_count"] = 0
        
        try:
            new_count = job() 
            if new_count is not None:
                RADAR_STATUS["last_new_count"] = new_count
                
            RADAR_STATUS["last_run_time"] = time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.error(f"Background task exception: {e}")
            RADAR_STATUS["last_new_count"] = 0
        finally:
            RADAR_STATUS["is_running"] = False
            RADAR_STATUS["status_text"] = "系统闲置中"

    background_tasks.add_task(_run_in_background)
    return True, "扫描任务已启动"

def job(target_keyword=None):
    """
    雷达核心任务流
    :param target_keyword: 如果指定了该关键字，本次爬虫和分析将只针对该词进行（用于 Agent 动态触发）
    """
    logger.info(f"Starting radar job pipeline (target_keyword={target_keyword})")
    
    reload_config()

    if target_keyword:
        global MONITOR_KEYWORDS, MONITOR_KEYWORD_LEVELS
        MONITOR_KEYWORDS = [target_keyword]
        MONITOR_KEYWORD_LEVELS = {target_keyword: "balanced"} # 临时任务默认给予 balanced 敏感度
        logger.info(f"🎯 临时接管监控配置，本次将专注抓取: {target_keyword}")

    if MONITOR_PLATFORMS:
        for platform in MONITOR_PLATFORMS:
            run_crawler_for_platform(platform)
    else:
        logger.warning("⚠️ MONITOR_PLATFORMS 为空，请检查系统设置！爬虫任务被跳过。")
        
    new_risk_count = run_analysis_pipeline()
    return new_risk_count

if __name__ == "__main__":
    reload_config()
    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("18:00").do(daily_summary_job)
    
    logger.info("Radar service started. Waiting for scheduled tasks...")
    while True:
        schedule.run_pending()
        time.sleep(60)