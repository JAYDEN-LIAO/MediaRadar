<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn">☰</view>
      <view class="title">舆情监控</view>
      <view class="action-btn" @click="goToSettings">⚙️</view>
    </view>
    
    <scroll-view scroll-y class="content">
      
      <view class="card summary-card">
        <view class="card-header">
          <text class="icon">📊</text>
          <text class="title">今日舆情简报</text>
          <text class="date">{{ today }}</text>
        </view>
        <view class="stats-row">
          <view class="stat-item">
            <view class="number">{{ todayNewCount }}</view>
            <view class="label">今日新增</view>
          </view>
          <view class="stat-item">
            <view class="number" :style="{ color: highRiskCount > 0 ? '#ff4d4f' : '#333' }">{{ highRiskCount }}</view>
            <view class="label">高风险</view>
          </view>
          <view class="stat-item">
            <view class="number">100%</view>
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
            <view class="positive" :style="{ width: posPct + '%' }"></view>
            <view class="neutral" :style="{ width: neuPct + '%' }"></view>
            <view class="negative" :style="{ width: negPct + '%' }"></view>
          </view>
          <view class="sentiment-labels">
            <text>{{ posPct }}%</text>
            <text>{{ neuPct }}%</text>
            <text>{{ negPct }}%</text>
          </view>
        </view>
      </view>

      <view class="card ai-summary-card">
        <view class="card-header">
          <text class="icon">🤖</text>
          <text class="title">AI 智能研判摘要</text>
        </view>
        <view class="summary-text">
          近期关于“{{ keyword }}”的讨论整体呈现以 <text style="font-weight: bold; color: #667eea;">{{ mainSentimentText }}</text> 为主的态势。今日共捕获到相关讨论 {{ todayNewCount }} 条。
        </view>
        
        <block v-if="highRiskCount > 0">
          <view class="warning-text">
            ⚠️ 发现 {{ highRiskCount }} 起高风险事件，建议公关/客服团队立刻排查并跟进。
          </view>
          <view class="alert-box" v-if="latestAlert">
            <view class="alert-item" @click="goToList">
              <view class="source">
                <text class="platform">{{ latestAlert.platform }}</text>
                <text class="dot">·</text>
                <text class="time">{{ latestAlert.create_time.substring(11, 16) }}</text>
              </view>
              <view class="text">{{ latestAlert.report }}</view>
            </view>
          </view>
        </block>
        
        <block v-else>
          <view class="warning-text" style="background-color: #f6ffed; color: #389e0d;">
            ✅ 今日暂未发现明显的高风险负面舆情，品牌口碑平稳。
          </view>
        </block>
      </view>

      <view class="card trend-card">
         <view class="card-header">
          <text class="icon">📈</text>
          <text class="title">近7日声量趋势</text>
        </view>
        <view class="chart-placeholder">
          [ 数据折线图展示区 ]
        </view>
      </view>

      <button class="view-all-btn" @click="startRadar">启动新一轮全网扫描</button>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

// 基础变量
const keyword = ref('加载中...') 
const today = ref(new Date().toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }))

// 数据统计变量
const todayNewCount = ref(0)
const highRiskCount = ref(0)
const posCount = ref(0)
const neuCount = ref(0)
const negCount = ref(0)

// 动态计算百分比
const total = computed(() => posCount.value + neuCount.value + negCount.value)
const posPct = computed(() => total.value === 0 ? 0 : Math.round((posCount.value / total.value) * 100))
const negPct = computed(() => total.value === 0 ? 0 : Math.round((negCount.value / total.value) * 100))
const neuPct = computed(() => total.value === 0 ? 0 : (100 - posPct.value - negPct.value)) // 保证加起来100%

// 动态 AI 文案
const mainSentimentText = computed(() => {
  if (total.value === 0) return '暂无数据'
  const max = Math.max(posCount.value, neuCount.value, negCount.value)
  if (max === posCount.value) return '正面讨论'
  if (max === negCount.value) return '负面情绪'
  return '中性声量'
})

const latestAlert = ref(null) // 最新的高风险帖子

// 路由
const goToSettings = () => uni.navigateTo({ url: '/pages/settings/settings' })
const goToList = () => uni.switchTab({ url: '/pages/list/list' })

// 🚀 读取真实的系统配置
const loadSystemConfig = () => {
  uni.request({
    url: 'http://127.0.0.1:8000/api/settings',
    method: 'GET',
    success: (res) => {
      if (res.data && res.data.code === 200) {
        const kws = res.data.data.keywords || []
        keyword.value = kws.length > 0 ? kws.join('、') : '未配置监控词'
      }
    }
  })
}

// 🚀 读取数据库舆情列表，并计算首页展示的数据
const loadDashboardData = () => {
  uni.request({
    url: 'http://127.0.0.1:8000/api/yq_list',
    method: 'GET',
    success: (res) => {
      if (res.data && res.data.code === 200) {
        const list = res.data.data
        
        // 构造今天的日期前缀，例如 "2026-03-18"
        const d = new Date()
        const todayStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        
        // 过滤出今天的帖子
        const todayData = list.filter(item => item.create_time && item.create_time.startsWith(todayStr))
        
        todayNewCount.value = todayData.length
        
        let pos = 0, neu = 0, neg = 0
        let recentNeg = null
        
        todayData.forEach(item => {
          if (item.sentiment === 'positive') pos++
          else if (item.sentiment === 'negative') {
            neg++
            if (!recentNeg) recentNeg = item // 取第一条遇到的负面（因为后端排序是倒序，所以第一条就是最新的）
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

// 🚀 触发后端扫描
const startRadar = () => {
  uni.showLoading({ title: '正在启动扫描...' })
  uni.request({
    url: 'http://127.0.0.1:8000/api/start_task',
    method: 'POST',
    success: (res) => {
      uni.hideLoading()
      if (res.data && res.data.code === 200) {
        uni.showToast({ title: '全网扫描已启动!', icon: 'success' })
        setTimeout(() => goToList(), 1500)
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

onMounted(() => {
  loadSystemConfig()
  loadDashboardData()
})
</script>

<style scoped>
/* ✨ 核心修复区：引入 box-sizing: border-box 解决右侧被裁切问题 */
view, text, scroll-view, button {
  box-sizing: border-box;
}

.page-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
  width: 100vw;
  overflow-x: hidden;
}

.header {
  height: 100rpx;
  background-color: #ffffff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32rpx;
  border-bottom: 2rpx solid #eee;
  z-index: 10;
}
.header .back-btn { font-size: 40rpx; color: #333; cursor: pointer; width: 60rpx; }
.header .action-btn { font-size: 40rpx; color: #333; cursor: pointer; width: 60rpx; text-align: right; }
.header .title { font-size: 36rpx; font-weight: 600; color: #333; }

.content { padding: 32rpx; padding-bottom: 120rpx; width: 100%; }

/* ✨ 新增全局的 card 样式，解决居中和背景问题 */
.card {
  background-color: #fff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.05);
  width: 100%;
}

.card-header { display: flex; align-items: center; margin-bottom: 24rpx; }
.card-header .icon { font-size: 40rpx; margin-right: 16rpx; }
.card-header .title { font-size: 32rpx; font-weight: 600; color: #333; }
.card-header .date { font-size: 24rpx; color: #999; margin-left: auto; }

.stats-row { display: flex; justify-content: space-around; padding: 16rpx 0 32rpx 0; border-bottom: 1px solid #f0f0f0; }
.stat-item { text-align: center; }
.stat-item .number { font-size: 56rpx; font-weight: 700; color: #333; }
.stat-item .label { font-size: 24rpx; color: #999; margin-top: 8rpx; }

.sentiment-section { padding: 32rpx 0 0 0; }
.section-title { font-size: 28rpx; color: #666; margin-bottom: 24rpx; }
.sentiment-row { display: flex; justify-content: space-around; margin-bottom: 24rpx; }
.sentiment-item { text-align: center; }
.sentiment-item .emoji { font-size: 56rpx; margin-bottom: 8rpx; }
.sentiment-item .type { font-size: 24rpx; color: #999; }
.sentiment-item .count { font-size: 36rpx; font-weight: 600; color: #333; margin-top: 4rpx; }

.sentiment-bar { display: flex; height: 16rpx; border-radius: 8rpx; overflow: hidden; margin-top: 24rpx; background-color: #eee;}
.sentiment-bar .positive { background: linear-gradient(90deg, #52c41a, #73d13d); transition: width 0.5s ease; }
.sentiment-bar .neutral { background: linear-gradient(90deg, #faad14, #ffc53d); transition: width 0.5s ease; }
.sentiment-bar .negative { background: linear-gradient(90deg, #ff4d4f, #ff7875); transition: width 0.5s ease; }
.sentiment-labels { display: flex; justify-content: space-between; margin-top: 16rpx; font-size: 24rpx; color: #999; }

.summary-text { font-size: 28rpx; line-height: 1.8; color: #666; }
.warning-text { margin-top: 24rpx; padding: 24rpx; background-color: #fff7e6; border-radius: 16rpx; font-size: 28rpx; line-height: 1.6; color: #d46b08; }

.alert-box { margin-top: 24rpx; }
.alert-item { padding: 24rpx; background-color: #fff2f0; border-radius: 16rpx; border-left: 6rpx solid #ff4d4f; }
.alert-item .source { display: flex; align-items: center; margin-bottom: 12rpx; }
.alert-item .platform { font-size: 24rpx; color: #ff4d4f; font-weight: 500; }
.alert-item .dot { margin: 0 12rpx; color: #ccc; }
.alert-item .time { font-size: 24rpx; color: #999; }
.alert-item .text { font-size: 28rpx; color: #333; line-height: 1.5; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }

.chart-placeholder { height: 240rpx; background-color: #f9f9f9; border-radius: 16rpx; display: flex; align-items: center; justify-content: center; color: #999; font-size: 28rpx; margin-top: 24rpx; }

.view-all-btn { width: 100%; padding: 20rpx 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; border-radius: 24rpx; color: #fff; font-size: 32rpx; font-weight: 500; margin-top: 8rpx; box-shadow: 0 10rpx 40rpx rgba(102, 126, 234, 0.4); }
</style>