// js/api.js
const API_BASE = "http://localhost:8000";

// 1. 获取最新数据并渲染列表
async function fetchLatestData() {
    try {
        const res = await fetch(`${API_BASE}/api/data/latest`);
        const json = await res.json();
        if (json.data && json.data.length > 0) {
            renderDataList(json.data);
        }
    } catch (e) {
        console.error("❌ 无法连接到后端 API:", e);
    }
}

// 2. 渲染前端卡片 (你需要根据 HTML 里真实的类名进行微调)
function renderDataList(dataArray) {
    // 假设舆情列表的容器类名为 .list-container 或 .content
    const container = document.querySelector('.content'); 
    if (!container) return;
    
    // 清空旧列表
    container.innerHTML = ''; 
    
    // 生成新的 HTML 结构
    dataArray.forEach(item => {
        let riskClass = item.risk_level === 'high' ? 'negative' : (item.risk_level === 'low' ? 'positive' : 'neutral');
        // 将风险等级转为中文标签
        let riskText = item.risk_level === 'high' ? '高风险' : (item.risk_level === 'low' ? '低风险' : '中风险');
        
        const cardHtml = `
        <div class="list-item ${riskClass}">
            <div class="list-item-header">
                <span class="platform-tag">${item.platform.toUpperCase()}</span>
                <span class="sentiment-tag ${riskClass}">${riskText}</span>
            </div>
            <div class="list-item-content">
                <strong>[${item.core_issue}]</strong> ${item.report}
            </div>
            <div class="list-item-footer" style="font-size: 12px; color: #888; margin-top: 8px;">
                <span>时间: ${item.create_time}</span>
            </div>
        </div>`;
        container.insertAdjacentHTML('beforeend', cardHtml);
    });
}

// 3. 启动雷达监控
async function startRadarTask(keyword) {
    try {
        alert(`正在启动 [${keyword}] 的舆情雷达...`);
        const res = await fetch(`${API_BASE}/api/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keywords: [keyword] })
        });
        const result = await res.json();
        alert(result.message);
    } catch (e) {
        alert("启动失败，请检查后端是否运行！");
    }
}

// 4. 初始化绑定事件与定时器
document.addEventListener('DOMContentLoaded', () => {
    // 获取开始按钮并绑定事件 (请确认你 HTML 里按钮的实际 id 或 class)
    const startBtn = document.querySelector('.start-btn'); // 替换为真实的按钮选择器
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            // 这里可以换成从页面输入框获取 keyword
            startRadarTask("北京银行"); 
        });
    }

    // 初次加载数据
    fetchLatestData();
    // 每 15 秒刷新一次
    setInterval(fetchLatestData, 15000);
});