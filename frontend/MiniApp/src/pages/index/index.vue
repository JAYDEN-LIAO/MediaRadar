<template>
  <view class="page-container">
    <view class="header">
      <view class="title">舆情监控</view>
    </view>
    
    <scroll-view scroll-y class="content-scroll">
      <view class="content-inner">
        
        <view class="settings-card">
          <view class="card-header">
            <view class="header-left">
              <text class="icon">📊</text>
              <text class="title">今日舆情简报</text>
            </view>
            <text class="date-tag">{{ today }}</text>
          </view>
          
          <view class="stats-row">
            <view class="stat-item">
              <view class="number">{{ todayNewCount }}</view>
              <view class="label">今日新增</view>
            </view>
            <view class="stat-item">
              <view class="number" :class="{ 'text-danger': highRiskCount > 0 }">{{ highRiskCount }}</view>
              <view class="label">高风险</view>
            </view>
            <view class="stat-item">
              <view class="number text-success">100%</view>
              <view class="label">入库率</view>
            </view>
          </view>
          
          <view class="sentiment-section">
            <view class="section-title">情感分布</view>
            <view class="sentiment-row">
              <view class="sentiment-item">
                <view class="emoji">😊</view>
                <view class="type">正面</view>
                <view class="count">{{ posCount }}</view>
              </view>
              <view class="sentiment-item">
                <view class="emoji">😐</view>
                <view class="type">中性</view>
                <view class="count">{{ neuCount }}</view>
              </view>
              <view class="sentiment-item">
                <view class="emoji">😠</view>
                <view class="type">负面</view>
                <view class="count">{{ negCount }}</view>
              </view>
            </view>
            
            <view class="sentiment-bar">
              <view class="bar-segment positive" :style="{ width: posPct + '%' }"></view>
              <view class="bar-segment neutral" :style="{ width: neuPct + '%' }"></view>
              <view class="bar-segment negative" :style="{ width: negPct + '%' }"></view>
            </view>
            <view class="sentiment-labels">
              <text>{{ posPct }}%</text>
              <text>{{ neuPct }}%</text>
              <text>{{ negPct }}%</text>
            </view>
          </view>
        </view>

        <view class="settings-card">
          <view class="card-header">
            <view class="header-left">
              <text class="icon">🤖</text>
              <text class="title">AI 智能研判摘要</text>
            </view>
          </view>
          
          <view class="summary-text">
            近期关于“{{ keyword }}”的讨论整体呈现以 <text class="highlight-text">{{ mainSentimentText }}</text> 为主的态势。今日共捕获到相关讨论 {{ todayNewCount }} 条。
          </view>
          
          <block v-if="highRiskCount > 0">
            <view class="warning-box danger">
              ⚠️ 发现 {{ highRiskCount }} 起高风险事件，建议公关/客服团队立刻排查并跟进。
            </view>
            
            <view class="alert-box" v-if="latestAlert">
              <view class="alert-item" @click="goToList">
                <view class="source">
                  <text class="platform">{{ latestAlert.platform }}</text>
                  <text class="dot">·</text>
                  <text class="time">{{ latestAlert.create_time.substring(11, 16) }}</text>
                </view>
                <view class="alert-text">{{ latestAlert.report }}</view>
              </view>
            </view>
          </block>
          
          <block v-else>
            <view class="warning-box safe">
              ✅ 今日暂未发现明显的高风险负面舆情，品牌口碑平稳。
            </view>
          </block>
        </view>

        <view class="settings-card">
           <view class="card-header">
            <view class="header-left">
              <text class="icon">📈</text>
              <text class="title">近7日声量趋势</text>
            </view>
          </view>
          <view class="chart-placeholder">
            [ 数据折线图展示区 ]
          </view>
        </view>

        <view class="action-container">
          <button class="primary-btn" @click="startRadar">
            {{ isWaitingForScan ? '扫描进行中...' : '启动新一轮全网扫描' }}
          </button>
        </view>
        
        <view class="bottom-spacer"></view>
      </view>
    </scroll-view>

    <movable-area class="fab-area">
      <movable-view 
        class="agent-fab-view" 
        direction="all" 
        :x="fabX" 
        :y="fabY" 
        :animation="true"
        @change="onFabChange"
        @touchend="onFabTouchEnd"
      >
        <view class="agent-fab" @click.stop="goToAgentChat">
          <text class="fab-text">AI</text>
        </view>
      </movable-view>
    </movable-area>

  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// 基础变量
const keyword = ref('加载中...') 
const today = ref(new Date().toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }))

// 数据统计变量
const todayNewCount = ref(0)
const highRiskCount = ref(0)
const posCount = ref(0)
const neuCount = ref(0)
const negCount = ref(0)

// 轮询控制变量
const isWaitingForScan = ref(false)
let pollTimer = null

// 组件销毁时清理定时器
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

// 动态计算百分比
const total = computed(() => posCount.value + neuCount.value + negCount.value)
const posPct = computed(() => total.value === 0 ? 0 : Math.round((posCount.value / total.value) * 100))
const negPct = computed(() => total.value === 0 ? 0 : Math.round((negCount.value / total.value) * 100))
const neuPct = computed(() => total.value === 0 ? 0 : (100 - posPct.value - negPct.value)) 

// 动态 AI 文案
const mainSentimentText = computed(() => {
  if (total.value === 0) return '暂无数据'
  const max = Math.max(posCount.value, neuCount.value, negCount.value)
  if (max === posCount.value) return '正面讨论'
  if (max === negCount.value) return '负面情绪'
  return '中性声量'
})

const latestAlert = ref(null) 

const goToList = () => uni.switchTab({ url: '/pages/list/list' })

// 读取真实的系统配置
const loadSystemConfig = () => {
  uni.request({
    url: 'http://127.0.0.1:8008/api/settings',
    method: 'GET',
    success: (res) => {
      if (res.data && res.data.code === 200) {
        const kws = res.data.data.keywords || []
        keyword.value = kws.length > 0 ? kws.join('、') : '未配置监控词'
      }
    }
  })
}

// 读取数据库舆情列表，并计算首页展示的数据
const loadDashboardData = () => {
  uni.request({
    url: 'http://127.0.0.1:8008/api/yq_list',
    method: 'GET',
    success: (res) => {
      if (res.data && res.data.code === 200) {
        const list = res.data.data
        
        const d = new Date()
        const todayStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        
        const todayData = list.filter(item => item.create_time && item.create_time.startsWith(todayStr))
        
        todayNewCount.value = todayData.length
        
        let pos = 0, neu = 0, neg = 0
        let recentNeg = null
        
        todayData.forEach(item => {
          if (item.sentiment === 'positive') pos++
          else if (item.sentiment === 'negative') {
            neg++
            if (!recentNeg) recentNeg = item 
          }
          else neu++
        })
        
        posCount.value = pos
        neuCount.value = neu
        negCount.value = neg
        highRiskCount.value = neg
        latestAlert.value = recentNeg
      }
    }
  })
}

// 🌟 轮询后端状态
const startPollingStatus = () => {
  if (pollTimer) clearInterval(pollTimer)
  
  pollTimer = setInterval(() => {
    uni.request({
      url: 'http://127.0.0.1:8008/api/radar_status',
      method: 'GET',
      success: (res) => {
        if (res.data && res.data.code === 200) {
          const statusData = res.data.data
          
          // 如果后端停止运行了，且前端正在等待结果
          if (!statusData.is_running && isWaitingForScan.value) {
            isWaitingForScan.value = false
            clearInterval(pollTimer)
            
            // 弹窗提示结果
            if (statusData.last_new_count > 0) {
              uni.showToast({ 
                title: `扫描完毕！新增 ${statusData.last_new_count} 条预警`, 
                icon: 'success', 
                duration: 3000 
              })
            } else {
              uni.showToast({ 
                title: '扫描完毕，暂无相关舆情', 
                icon: 'none', 
                duration: 3000 
              })
            }
            
            // 重新拉取一次列表数据刷新看板
            loadDashboardData()
          }
        }
      },
      fail: () => {
        console.error('获取状态失败，停止轮询')
        clearInterval(pollTimer)
      }
    })
  }, 3000) // 3秒问一次后端
}

// 🚀 触发后端扫描
const startRadar = () => {
  if (isWaitingForScan.value) return // 防止连点
  
  uni.showLoading({ title: '启动扫描中...' })
  uni.request({
    url: 'http://127.0.0.1:8008/api/start_task',
    method: 'POST',
    success: (res) => {
      uni.hideLoading()
      if (res.data && res.data.code === 200) {
        uni.showToast({ title: '开始全面扫描，请稍候', icon: 'none' })
        isWaitingForScan.value = true // 标记开始等待
        startPollingStatus() // 启动轮询
      } else {
        uni.showToast({ title: res.data.msg || '启动失败', icon: 'none' })
      }
    },
    fail: () => {
      uni.hideLoading()
      uni.showToast({ title: '网络请求失败，请检查后端', icon: 'none' })
    }
  })
}

const goToAgentChat = () => {
  uni.navigateTo({
    url: '/pages/chat/agentChat'
  });
}

// ==========================================
// 【新增】智能体拖拽与吸附边缘逻辑
// ==========================================
const sysInfo = uni.getSystemInfoSync();
const screenWidth = sysInfo.windowWidth;
const screenHeight = sysInfo.windowHeight;

// 将设计稿的 120rpx 转换为真实像素，用于精确计算边界
const fabSizePx = uni.upx2px(120); 
const marginPx = uni.upx2px(30); // 留出一点边距，避免贴太死

// 按钮初始位置：靠右、偏下
const fabX = ref(screenWidth - fabSizePx - marginPx);
const fabY = ref(screenHeight - uni.upx2px(260)); 

// 记录当前拖动的实时位置
let currentX = fabX.value;
let currentY = fabY.value;

const onFabChange = (e) => {
  // 只响应用户手指拖动 (排除动画过程触发的 change)
  if (e.detail.source === 'touch') {
    currentX = e.detail.x;
    currentY = e.detail.y;
  }
};

const onFabTouchEnd = () => {
  // 核心吸附逻辑：松手时，判断中心点在屏幕左半边还是右半边
  const isLeftHalf = (currentX + fabSizePx / 2) < (screenWidth / 2);
  
  if (isLeftHalf) {
    fabX.value = marginPx; // 吸附到左边缘
  } else {
    fabX.value = screenWidth - fabSizePx - marginPx; // 吸附到右边缘
  }
  
  // Y轴保持松手时的位置不变
  fabY.value = currentY; 
};

onMounted(() => {
  loadSystemConfig()
  loadDashboardData()
})

</script>

<style scoped>
/* 保持全局设置以防止右侧裁切 */
view, text, scroll-view, button {
  box-sizing: border-box;
}

/* 统一高级灰底色及布局 */
.page-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #F4F5F7;
  overflow: hidden;
}

/* 统一头部样式，带磨砂玻璃效果 */
.header { 
  height: 100rpx; background-color: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px);
  display: flex; justify-content: center; align-items: center;
  padding: 0 32rpx; border-bottom: 1px solid rgba(0,0,0,0.05); z-index: 10; 
}
.header .title { font-size: 34rpx; font-weight: 600; color: #111827; letter-spacing: 1rpx;}

/* 统一滚动区域，修复卡顿Bug */
.content-scroll { flex: 1; height: 0; width: 100%; }
.content-inner { padding: 32rpx; }
.bottom-spacer { height: 60rpx; }

/* 统一极简卡片风格 */
.settings-card { 
  background-color: #ffffff; border-radius: 24rpx; padding: 32rpx; 
  margin-bottom: 28rpx; box-shadow: 0 4rpx 24rpx rgba(0,0,0,0.02); width: 100%;
}
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32rpx; }
.header-left { display: flex; align-items: center; }
.header-left .icon { font-size: 36rpx; margin-right: 16rpx; }
.header-left .title { font-size: 32rpx; font-weight: 600; color: #111827; }

/* 日期标签 */
.date-tag { font-size: 24rpx; color: #4F46E5; background: rgba(79, 70, 229, 0.1); padding: 4rpx 16rpx; border-radius: 20rpx; font-weight: 500;}

/* 数据概览区 */
.stats-row { display: flex; justify-content: space-around; padding: 16rpx 0 32rpx 0; border-bottom: 1px solid #F3F4F6; margin-bottom: 24rpx;}
.stat-item { text-align: center; }
.stat-item .number { font-size: 48rpx; font-weight: 700; color: #111827; margin-bottom: 8rpx; }
.stat-item .label { font-size: 24rpx; color: #6B7280; }
.text-danger { color: #EF4444 !important; }
.text-success { color: #10B981 !important; }

/* 情感分布区 */
.section-title { font-size: 28rpx; color: #374151; margin-bottom: 24rpx; font-weight: 500;}
.sentiment-row { display: flex; justify-content: space-around; margin-bottom: 24rpx; }
.sentiment-item { text-align: center; }
.sentiment-item .emoji { font-size: 50rpx; margin-bottom: 12rpx; }
.sentiment-item .type { font-size: 24rpx; color: #6B7280; }
.sentiment-item .count { font-size: 32rpx; font-weight: 600; color: #111827; margin-top: 8rpx; }

/* 进度条保持动态绑定 */
.sentiment-bar { height: 16rpx; border-radius: 8rpx; display: flex; overflow: hidden; background: #eee; margin-top: 24rpx; }
.bar-segment { transition: width 0.5s ease; }
.bar-segment.positive { background-color: #10B981; }
.bar-segment.neutral { background-color: #FBBF24; }
.bar-segment.negative { background-color: #EF4444; }
.sentiment-labels { display: flex; justify-content: space-between; margin-top: 16rpx; font-size: 22rpx; color: #9CA3AF; }

/* AI 摘要区 */
.summary-text { font-size: 28rpx; line-height: 1.6; color: #4B5563; }
.highlight-text { font-weight: 600; color: #4F46E5; }

/* 提示框高级感 */
.warning-box { padding: 24rpx; border-radius: 12rpx; margin-top: 24rpx; font-size: 26rpx; line-height: 1.5; }
.warning-box.danger { background-color: #FEF2F2; color: #991B1B; border-left: 6rpx solid #EF4444; }
.warning-box.safe { background-color: #F0FDF4; color: #065F46; border-left: 6rpx solid #10B981; }

.alert-box { margin-top: 24rpx; }
.alert-item { padding: 24rpx; background-color: #F9FAFB; border-radius: 16rpx; border: 1px solid #F3F4F6; }
.alert-item .source { display: flex; align-items: center; margin-bottom: 12rpx; }
.alert-item .platform { font-size: 24rpx; color: #EF4444; font-weight: 600; }
.alert-item .dot { margin: 0 12rpx; color: #D1D5DB; }
.alert-item .time { font-size: 24rpx; color: #9CA3AF; }
.alert-text { font-size: 28rpx; color: #374151; line-height: 1.5; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }

.chart-placeholder { height: 240rpx; background-color: #F9FAFB; border-radius: 16rpx; border: 1px dashed #E5E7EB; display: flex; align-items: center; justify-content: center; color: #9CA3AF; font-size: 28rpx; margin-top: 24rpx; }

/* 统一按钮风格 */
.action-container { padding: 12rpx 0; }
.primary-btn { 
  width: 100%; padding: 24rpx 0; background-color: #4F46E5; 
  border-radius: 16rpx; color: #ffffff; font-size: 30rpx; 
  display: flex; justify-content: center; align-items: center; font-weight: 500;
  box-shadow: 0 8rpx 20rpx rgba(79, 70, 229, 0.2);
  border: none; margin: 0;
}
.primary-btn:active { opacity: 0.9; transform: scale(0.99); }

/* ==========================================
   新增：全屏拖拽区域与悬浮按钮样式
========================================== */
.fab-area {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  pointer-events: none; /* 让用户能够穿透拖拽层，点击到下方的列表 */
}

.agent-fab-view {
  width: 120rpx;
  height: 120rpx;
  pointer-events: auto; /* 让按钮自身恢复点击和触摸响应 */
}

.agent-fab {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #4F46E5, #3B82F6);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 10rpx 30rpx rgba(79, 70, 229, 0.4);
  transition: transform 0.2s ease; /* 点击缩放效果 */
}

.agent-fab:active {
  transform: scale(0.9);
}

.fab-text {
  color: #FFFFFF;
  font-size: 44rpx;
  font-weight: 800;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  letter-spacing: 2rpx;
}
</style>