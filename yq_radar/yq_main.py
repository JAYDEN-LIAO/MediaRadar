# yq_radar/yq_main.py
import subprocess
import time
import schedule
import os
import threading


# 修改 1：引入批量写入函数 mark_processed_batch
from db_manager import get_unprocessed_posts, mark_processed_batch, save_ai_result, get_latest_results # 【修改】引入新增的 db 方法
# 修改 2：统一在顶部导入所需的 LLM 模块
from llm_pipeline import process_post, call_llm, cluster_related_posts
from notifier import send_alert

# 全局状态字典，供前端查询雷达是否在运行
RADAR_STATUS = {
    "is_running": False,
    "status_text": "系统闲置中",
    "last_run_time": "暂无"
}

# ================= 配置区 =================
MONITOR_KEYWORD = "北京银行"
MONITOR_PLATFORMS = ["wb"] # 如果想同时监控多个，可以填 ["wb", "xhs"]
# MediaCrawler 默认生成的数据库相对路径 (这里假设 yq_radar 和 data 在同一级目录)
CRAWLER_DB_PATH = "../crawler_core/database/sqlite_tables.db"
# ==========================================

def run_crawler_for_platform(platform):
    """通过命令行调起底层的 MediaCrawler 抓取最新数据"""
    print(f"⏳ 开始抓取平台: {platform.upper()}...")
    try:
        # 【修改重点】：cwd 改为 crawler_core，确保调用的是内部打包好的爬虫
        subprocess.run(
            ["uv", "run", "main.py", "--platform", platform, "--type", "search", "--save_data_option", "sqlite", "--headless", "no"],
            cwd="../crawler_core", 
            check=True
        )
        print(f"✅ {platform.upper()} 数据抓取完成！")
    except subprocess.CalledProcessError as e:
        print(f"❌ 抓取平台 {platform} 时发生错误: {e}")

def run_analysis_pipeline():
    """批量读取数据 -> AI 筛选 -> 话题聚类 -> 研判与聚合报警"""
    for platform in MONITOR_PLATFORMS:
        print(f"\n🔍 正在读取 {platform.upper()} 的最新未分析数据...")
        
        posts = get_unprocessed_posts(CRAWLER_DB_PATH, platform)
        if not posts:
            print(f"📭 {platform.upper()} 暂无未处理数据。")
            continue
            
        print(f"📦 发现 {len(posts)} 条新数据，开始 [阶段1: 噪音过滤]...")
        
        relevant_posts = []
        processed_records = [] # <--- 修改 3：准备一个小推车，用于装载本批次所有处理过的 ID
        
        # 构建一个字典方便通过 ID 快速找回完整帖子数据
        post_dict = {p["post_id"]: p for p in posts} 
        
        # 1. 逐条进行基础筛选 (过滤广告、无关)
        for idx, p in enumerate(posts, 1):
            print(f"  -> [{idx}/{len(posts)}] 筛选帖子 ID: {p['post_id']} ... ", end="\r")
            
            screener_prompt = f"""你是一个严谨的数据筛选员。目标实体：【{MONITOR_KEYWORD}】。判断内容是否真正在讨论该实体。输出JSON: {{"is_relevant": true/false, "reason": "..."}}"""
            text_to_analyze = f"标题: {p['title']}\n正文: {p['content'][:500]}"
            
            res = call_llm(screener_prompt, text_to_analyze)
            if res.get("is_relevant"):
                relevant_posts.append(p)
            
            # 将帖子 ID 和平台放入小推车，不再每次单独开关数据库
            processed_records.append((p["post_id"], platform))
            time.sleep(0.5) # 依然保留延时，防止触发大模型 API 频率限制

        print(f"\n✅ 筛选完成！相关: {len(relevant_posts)} 条 / 噪音: {len(posts) - len(relevant_posts)} 条")

        # <--- 修改 4：循环结束后，一车拉走，一次性批量写入数据库！
        if processed_records:
            mark_processed_batch(processed_records)
            print(f"💾 已将 {len(processed_records)} 条数据批量标记为[已处理]。")

        if not relevant_posts:
            print("🟢 本批次无相关风险事件。")
            continue

        print(f"🔗 针对 {len(relevant_posts)} 条相关数据，开始 [阶段2: 话题聚类]...")
        
        # 2. 调用新增的聚类模型
        clusters = cluster_related_posts(relevant_posts, MONITOR_KEYWORD)
        
        print(f"📊 成功聚类为 {len(clusters)} 个核心话题。开始 [阶段3: 深度研判]...")
        
        # 3. 按“话题”进行深度研判与报警
        for cluster in clusters:
            topic_name = cluster.get("topic_name", "未知话题")
            post_ids = cluster.get("post_ids", [])
            if not post_ids: continue
            
            # 把这个话题下的所有帖子内容拼起来（限制长度防超载）
            combined_text = ""
            urls = []
            for pid in post_ids:
                if pid in post_dict:
                    combined_text += f"【帖子】{post_dict[pid]['title']}\n"
                    urls.append(post_dict[pid]['url'])
                    
            print(f"  -> 研判话题: [{topic_name}] (包含 {len(urls)} 条来源) ... ", end="")
            
            # 伪造一个综合的 post 数据送入你原有的 process_post 的【阶段2】和【阶段3】
            mock_post = {
                "title": f"聚合话题：{topic_name}",
                "content": combined_text[:2000] # 截断保护
            }
            
            result = process_post(mock_post, MONITOR_KEYWORD)
            
            # 【修改】：传入 p['title']、p['content'] 和 p['url']
            save_ai_result(
                post_id=p["post_id"], 
                platform=platform, 
                keyword=MONITOR_KEYWORD, 
                title=p.get("title", ""),          # <--- 新增：传入标题
                content=p.get("content", ""),      # <--- 新增：传入正文
                url=p.get("url", ""),              # <--- 新增：传入链接
                risk_level=result.get("risk_level", "low"), 
                core_issue=result.get("core_issue", "无异常"), 
                report=result.get("report", result.get("reason", ""))
            )

            if result["status"] == "alert":
                print(f"🚨 触发预警！(风险: {result.get('risk_level')})")
                
                # 触发通知，传入列表而不是单个 URL
                send_alert(
                    keyword=MONITOR_KEYWORD,
                    platform=platform,
                    risk_level=result["risk_level"],
                    core_issue=topic_name, 
                    report=result["report"],
                    urls=urls # <--- 注意这里传入的是列表
                )
            else:
                print("安全通过")


def api_start_task(keywords: list):
    """供 FastAPI 调用的非阻塞启动接口"""
    if RADAR_STATUS["is_running"]:
        return False, "雷达正在运行中，请勿重复启动"
    
    global MONITOR_KEYWORD
    if keywords and len(keywords) > 0:
        MONITOR_KEYWORD = keywords[0] # 更新监控关键词
        
    def _run_in_background():
        RADAR_STATUS["is_running"] = True
        RADAR_STATUS["status_text"] = f"正在监控: {MONITOR_KEYWORD}"
        try:
            job() # 执行原有业务闭环
            RADAR_STATUS["last_run_time"] = time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"后台任务异常: {e}")
        finally:
            RADAR_STATUS["is_running"] = False
            RADAR_STATUS["status_text"] = "系统闲置中"

    # 启动后台线程
    threading.Thread(target=_run_in_background).start()
    return True, "监控任务已启动"

def job():
    """单次完整的监控任务闭环"""
    print("\n" + "*"*50)
    print(f"⏰ 任务开始执行: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("*"*50)
    
    # 步骤 1：触发爬虫主动搜集
    for platform in MONITOR_PLATFORMS:
        run_crawler_for_platform(platform)
        
    # 步骤 2：对新数据进行 AI 研判并报警
    run_analysis_pipeline()
    
    print("🎉 本轮监控任务圆满结束，进入待机状态。\n")

if __name__ == "__main__":
    print("🚀 舆情早期监控雷达 V2.0 (微批处理版) 启动成功！")
    
    # 1. 启动时先立刻执行一次，方便你调试
    job()
    
    # 2. 配置定时任务
    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("13:00").do(job)
    schedule.every().day.at("18:00").do(job)
    
    print("⏳ 定时任务已加载，程序将持续在后台运行...")
    # 3. 进入死循环阻塞，等待定时器触发
    while True:
        schedule.run_pending()
        time.sleep(10)