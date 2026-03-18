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
            <view class="number">24</view>
            <view class="label">今日新增</view>
          </view>
          <view class="stat-item">
            <view class="number" style="color: #ff4d4f;">2</view>
            <view class="label">高风险</view>
          </view>
          <view class="stat-item">
            <view class="number">86%</view>
            <view class="label">处理率</view>
          </view>
        </view>
        
        <view class="sentiment-section">
          <view class="section-title">情感分布</view>
          <view class="sentiment-row">
            <view class="sentiment-item">
              <view class="emoji">😊</view>
              <view class="type">正面</view>
              <view class="count">15</view>
            </view>
            <view class="sentiment-item">
              <view class="emoji">😐</view>
              <view class="type">中性</view>
              <view class="count">6</view>
            </view>
            <view class="sentiment-item">
              <view class="emoji">😠</view>
              <view class="type">负面</view>
              <view class="count">3</view>
            </view>
          </view>
          <view class="sentiment-bar">
            <view class="positive" style="width: 61%;"></view>
            <view class="neutral" style="width: 26%;"></view>
            <view class="negative" style="width: 13%;"></view>
          </view>
          <view class="sentiment-labels">
            <text>61%</text>
            <text>26%</text>
            <text>13%</text>
          </view>
        </view>
      </view>

      <view class="card ai-summary-card">
        <view class="card-header">
          <text class="icon">🤖</text>
          <text class="title">AI 智能研判摘要</text>
        </view>
        <view class="summary-text">
          近期关于“{{ keyword }}”的讨论整体趋于平稳。正面讨论主要集中在“福利活动”及“医银合作”等方面。
        </view>
        <view class="warning-text">
          ⚠️ 发现 1 起高风险事件：大量用户在微博反馈App更新后闪退，建议技术团队立刻排查。
        </view>
        <view class="alert-box">
          <view class="alert-item" @click="goToList">
            <view class="source">
              <text class="platform">微博</text>
              <text class="dot">·</text>
              <text class="time">10:30</text>
            </view>
            <view class="text">[App闪退] 大量用户反馈更新后在启动时直接闪退...</view>
          </view>
        </view>
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
import { ref } from 'vue'

const keyword = ref('北京银行')
const today = ref(new Date().toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }))

const goToSettings = () => uni.navigateTo({ url: '/pages/settings/settings' })
const goToList = () => uni.switchTab({ url: '/pages/list/list' })

// 🚀 核心改造：点击按钮，请求后端真实启动爬虫
const startRadar = () => {
  uni.showLoading({ title: '正在启动雷达...' })
  
  uni.request({
    url: 'http://127.0.0.1:8000/api/start_task',
    method: 'POST',
    data: {
      keyword: keyword.value // 把页面上的关键词传给后端
    },
    success: (res) => {
      uni.hideLoading()
      if (res.data && res.data.code === 200) {
        uni.showToast({ title: '扫描已在后台启动!', icon: 'success' })
        // 启动成功后，我们可以跳转到列表页去等数据
        setTimeout(() => {
          goToList()
        }, 1500)
      } else {
        // 如果后端返回 400（比如雷达已经在运行中了）
        uni.showToast({ title: res.data.msg || '启动失败', icon: 'none' })
      }
    },
    fail: (err) => {
      uni.hideLoading()
      uni.showToast({ title: '网络请求失败，请检查后端', icon: 'none' })
      console.error(err)
    }
  })
}
</script>

<style scoped>
.content { padding: 32rpx; padding-bottom: 120rpx; }
.card-header .date { font-size: 24rpx; color: #999; margin-left: auto; }

.stats-row { display: flex; justify-content: space-around; padding: 32rpx 0; border-bottom: 1px solid #f0f0f0; }
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

.sentiment-bar { display: flex; height: 16rpx; border-radius: 8rpx; overflow: hidden; margin-top: 24rpx; }
.sentiment-bar .positive { background: linear-gradient(90deg, #52c41a, #73d13d); }
.sentiment-bar .neutral { background: linear-gradient(90deg, #faad14, #ffc53d); }
.sentiment-bar .negative { background: linear-gradient(90deg, #ff4d4f, #ff7875); }
.sentiment-labels { display: flex; justify-content: space-between; margin-top: 16rpx; font-size: 24rpx; color: #999; }

.summary-text { font-size: 28rpx; line-height: 1.8; color: #666; }
.warning-text { margin-top: 24rpx; padding: 24rpx; background-color: #fff7e6; border-radius: 16rpx; font-size: 28rpx; line-height: 1.6; color: #d46b08; }

.alert-box { margin-top: 24rpx; }
.alert-item { padding: 24rpx; background-color: #fff2f0; border-radius: 16rpx; border-left: 6rpx solid #ff4d4f; }
.alert-item .source { display: flex; align-items: center; margin-bottom: 12rpx; }
.alert-item .platform { font-size: 24rpx; color: #ff4d4f; font-weight: 500; }
.alert-item .dot { margin: 0 12rpx; color: #ccc; }
.alert-item .time { font-size: 24rpx; color: #999; }
.alert-item .text { font-size: 28rpx; color: #333; line-height: 1.5; }

.chart-placeholder { height: 240rpx; background-color: #f9f9f9; border-radius: 16rpx; display: flex; align-items: center; justify-content: center; color: #999; font-size: 28rpx; margin-top: 24rpx; }

.view-all-btn { width: 100%; padding: 20rpx 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; border-radius: 24rpx; color: #fff; font-size: 32rpx; font-weight: 500; margin-top: 8rpx; box-shadow: 0 10rpx 40rpx rgba(102, 126, 234, 0.4); }
</style>