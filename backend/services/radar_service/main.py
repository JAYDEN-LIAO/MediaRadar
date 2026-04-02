# backend/services/radar_service/main.py
import subprocess
import time
import schedule
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

CRAWLER_DIR = os.path.join(BACKEND_DIR, "services", "crawler_service")

from core.logger import get_logger
from core.context import set_task_context

logger = get_logger("radar.main")
from core.config import settings
from .db_manager import get_unprocessed_posts, mark_processed_batch, save_ai_result, get_system_settings
from .schemas import ScreenerResult
from .notifier import send_alert
from .pipeline import RadarPipeline, PipelineConfig

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

async def run_analysis_pipeline_async():
    """使用 RadarPipeline 执行完整分析流程（多平台 asyncio 并行）。"""
    import asyncio

    async def _run_single_platform(platform: str) -> int:
        """单个平台的完整 Pipeline（抓取 → 分析 → 持久化）。"""
        logger.info(f"[Pipeline Mode] Analyzing {platform.upper()}...")
        posts = get_unprocessed_posts(settings.CRAWLER_DB_PATH, platform)
        if not posts:
            return 0

        all_post_ids = [p["post_id"] for p in posts]

        config = PipelineConfig(
            keywords=MONITOR_KEYWORDS,
            keyword_levels=MONITOR_KEYWORD_LEVELS,
            platform=platform,
            alert_negative=ALERT_NEGATIVE,
        )
        pipeline = RadarPipeline(config)
        results = await pipeline.run(posts)

        # 批量标记已处理
        if all_post_ids:
            processed_records = [(pid, platform) for pid in all_post_ids]
            mark_processed_batch(processed_records)

        # 保存结果入库
        new_count = 0
        for pr in results:
            save_ai_result(
                post_id=pr.post_id,
                platform=pr.platform,
                keyword=pr.keyword,
                title=pr.title,
                content=pr.content,
                url=pr.url,
                risk_level=pr.risk_level,
                core_issue=pr.core_issue,
                report=pr.report,
                publish_time=pr.publish_time,
                sentiment=getattr(pr, 'sentiment', 'Neutral'),
            )
            new_count += 1
        return new_count

    # 所有平台并发（各平台独立运行，无依赖）
    tasks = [
        _run_single_platform(platform)
        for platform in MONITOR_PLATFORMS
    ]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 汇总结果（过滤异常）
    total_new_count = 0
    for i, result in enumerate(all_results):
        platform = MONITOR_PLATFORMS[i]
        if isinstance(result, Exception):
            logger.error(f"⚠️ 平台 {platform} 执行异常: {result}")
        else:
            total_new_count += result
            logger.info(f"[Pipeline Mode] {platform.upper()} 完成，新增 {result} 条")

    return total_new_count


def run_analysis_pipeline():
    """同步入口，内部启动 asyncio 事件循环。"""
    import asyncio
    return asyncio.run(run_analysis_pipeline_async())


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