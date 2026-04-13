<template>
  <view class="page-container">
    <view class="header">
      <view class="status-dot"></view>
      <view class="title">舆情监控</view>
      <text class="date">{{ today }}</text>
    </view>

    <scroll-view scroll-y class="content-scroll">
      <view class="content-inner">

        <view class="card card-primary">
          <view class="card-header">
            <view class="header-left">
              <text class="section-title">今日概览</text>
            </view>
            <view class="keyword-tag">{{ keyword }}</view>
          </view>

          <view class="stats-row">
            <view class="stat-item">
              <view class="number">{{ todayNewCount }}</view>
              <view class="label">今日新增</view>
            </view>
            <view class="stat-divider"></view>
            <view class="stat-item">
              <view class="number" :class="{ 'num-danger': highRiskCount > 0 }">{{ highRiskCount }}</view>
              <view class="label">高风险</view>
            </view>
            <view class="stat-divider"></view>
            <view class="stat-item">
              <view class="number num-success">100%</view>
              <view class="label">入库率</view>
            </view>
          </view>
        </view>

        <view class="card">
          <view class="card-header">
            <text class="section-title">情感分布</text>
          </view>

          <view class="sentiment-bar-container">
            <view class="sentiment-bar">
              <view class="bar-segment positive" :style="{ width: posPct + '%' }"></view>
              <view class="bar-segment neutral" :style="{ width: neuPct + '%' }"></view>
              <view class="bar-segment negative" :style="{ width: negPct + '%' }"></view>
            </view>
            <view class="sentiment-legend">
              <view class="legend-item">
                <view class="legend-dot positive"></view>
                <text class="legend-label">正面</text>
                <text class="legend-value">{{ posPct }}%</text>
              </view>
              <view class="legend-item">
                <view class="legend-dot neutral"></view>
                <text class="legend-label">中性</text>
                <text class="legend-value">{{ neuPct }}%</text>
              </view>
              <view class="legend-item">
                <view class="legend-dot negative"></view>
                <text class="legend-label">负面</text>
                <text class="legend-value">{{ negPct }}%</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 话题热度榜 -->
        <view class="card" v-if="topTopics.length > 0">
          <view class="card-header">
            <text class="section-title">话题热度榜</text>
            <text class="more-link" @click="goToTopicList">全部 ›</text>
          </view>
          <view class="topic-rank-list">
            <view
              class="topic-rank-item"
              v-for="(item, index) in topTopics"
              :key="index"
              @click="goToTopicDetail(item)"
            >
              <view class="rank-num" :class="{ top: index < 3 }">{{ index + 1 }}</view>
              <view class="rank-content">
                <view class="rank-title-row">
                  <view class="risk-dot" :class="item.risk_class"></view>
                  <text class="rank-title">{{ item.topic_name || '未知话题' }}</text>
                </view>
                <view class="rank-meta">
                  <text class="rank-platforms">{{ (item.platforms || []).join('、') }}</text>
                  <text class="rank-count">{{ item.post_count }}条</text>
                </view>
              </view>
              <text class="rank-arrow">›</text>
            </view>
          </view>
        </view>

        <view class="card">
          <view class="card-header">
            <text class="section-title">AI 智能研判摘要</text>
          </view>

          <view class="summary-text" v-if="todaySummary">
            {{ todaySummary.summary }}
          </view>
          <view class="summary-text" v-else>
            近期关于"<text class="highlight">{{ keyword }}</text>"的讨论整体呈现以 <text class="highlight">{{ mainSentimentText }}</text> 为主的态势。今日共捕获到相关讨论 <text class="highlight">{{ todayNewCount }}</text> 条。
          </view>

          <!-- 最热话题 & 风险升级话题 -->
          <view class="topic-pills" v-if="todaySummary && todaySummary.hottest_topic">
            <view class="topic-pill-label">最热话题</view>
            <view class="topic-pill">{{ todaySummary.hottest_topic }}</view>
          </view>
          <view class="escalating-list" v-if="todaySummary && todaySummary.escalating_topics && todaySummary.escalating_topics.length > 0">
            <view class="escalating-label">风险升级中</view>
            <view class="escalating-item" v-for="(t, i) in todaySummary.escalating_topics" :key="i">{{ t }}</view>
          </view>

          <block v-if="highRiskCount > 0">
            <view class="alert-box alert-danger">
              <view class="alert-indicator"></view>
              <view class="alert-content">
                <text class="alert-title">高风险预警</text>
                <text class="alert-desc">发现 {{ highRiskCount }} 起高风险事件，建议公关团队立刻跟进处理</text>
              </view>
            </view>

            <view class="latest-alert" v-if="latestAlert">
              <view class="alert-meta">
                <view class="platform-dot" :class="latestAlert.platform"></view>
                <text class="platform-name">{{ getPlatformName(latestAlert.platform) }}</text>
                <text class="dot-sep">·</text>
                <text class="alert-time">{{ latestAlert.create_time.substring(11, 16) }}</text>
              </view>
              <view class="alert-report">{{ latestAlert.report }}</view>
              <view class="alert-action" @click="goToList">查看详情 <text class="arrow">→</text></view>
            </view>
          </block>

          <block v-else>
            <view class="alert-box alert-safe">
              <view class="alert-indicator"></view>
              <view class="alert-content">
                <text class="alert-title">暂无高风险</text>
                <text class="alert-desc">今日暂未发现明显负面舆情，品牌口碑平稳</text>
              </view>
            </view>
          </block>
        </view>

        <view class="card">
          <view class="card-header">
            <text class="section-title">近7日声量趋势</text>
          </view>
          <!-- 7日声量趋势图（有数据时） -->
          <view class="trend-chart" v-if="volumeData.days && volumeData.days.length > 0">
            <view class="trend-legend">
              <view class="legend-item">
                <view class="legend-bar total-bar"></view>
                <text class="legend-label">总声量</text>
              </view>
              <view class="legend-item">
                <view class="legend-bar neg-bar"></view>
                <text class="legend-label">负面声量</text>
              </view>
            </view>
            <view class="trend-bars">
              <view class="bar-item" v-for="(day, i) in volumeData.days" :key="i">
                <view class="bar-col">
                  <view
                    class="bar total-bar"
                    :style="{ height: (volumeData.volumes[i] || 0) > 0 ? Math.max(10, (volumeData.volumes[i] / volumeData.total * 140 || 0)) + 'rpx' : '4rpx' }"
                  ></view>
                  <view
                    class="bar neg-bar"
                    :style="{ height: (volumeData.negative_volumes[i] || 0) > 0 ? Math.max(4, (volumeData.negative_volumes[i] / volumeData.total * 140 || 0)) + 'rpx' : '4rpx' }"
                  ></view>
                </view>
                <text class="bar-label">{{ day }}</text>
              </view>
            </view>
          </view>
          <!-- 无数据时显示空状态 -->
          <view class="chart-placeholder" v-else>
            <text class="placeholder-text">近7日暂无数据</text>
          </view>
        </view>

        <view class="action-container">
          <button class="primary-btn" @click="startRadar">
            {{ isWaitingForScan ? '扫描进行中...' : '启动全网扫描' }}
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
import { getTopicList, getVolumeStats, getTodaySummary } from '../../utils/api.js'

const keyword = ref('加载中...')
const today = ref(new Date().toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }))

const todayNewCount = ref(0)
const highRiskCount = ref(0)
const posCount = ref(0)
const neuCount = ref(0)
const negCount = ref(0)

const isWaitingForScan = ref(false)
let pollTimer = null

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

const total = computed(() => posCount.value + neuCount.value + negCount.value)
const posPct = computed(() => total.value === 0 ? 0 : Math.round((posCount.value / total.value) * 100))
const negPct = computed(() => total.value === 0 ? 0 : Math.round((negCount.value / total.value) * 100))
const neuPct = computed(() => total.value === 0 ? 0 : (100 - posPct.value - negPct.value))

const mainSentimentText = computed(() => {
  if (total.value === 0) return '暂无数据'
  const max = Math.max(posCount.value, neuCount.value, negCount.value)
  if (max === posCount.value) return '正面讨论'
  if (max === negCount.value) return '负面情绪'
  return '中性声量'
})

const latestAlert = ref(null)

// 话题热度榜
const topicList = ref([])

// 近7日声量数据
const volumeData = ref({ days: [], volumes: [], negative_volumes: [], total: 0, negative_total: 0 })

// 今日AI摘要
const todaySummary = ref(null)

const getPlatformName = (val) => {
  const names = { wb: '微博', xhs: '小红书', bili: 'B站', zhihu: '知乎', dy: '抖音', ks: '快手', tieba: '贴吧' }
  return names[val] || val
}

// 话题热度榜（取前5，按post_count降序，优先负面）
const topTopics = computed(() => {
  return [...topicList.value]
    .sort((a, b) => {
      // 负面优先
      if (a.risk_class === 'negative' && b.risk_class !== 'negative') return -1
      if (b.risk_class === 'negative' && a.risk_class !== 'negative') return 1
      return (b.post_count || 0) - (a.post_count || 0)
    })
    .slice(0, 5)
})

// 加载话题列表
const loadTopics = () => {
  getTopicList({ limit: 50 })
    .then(res => {
      if (res && res.code === 200) {
        topicList.value = res.data || []
      }
    })
    .catch(() => {})
}

// 加载7日声量数据
const loadVolumeStats = () => {
  getVolumeStats()
    .then(res => {
      if (res && res.code === 200) {
        volumeData.value = res.data || { days: [], volumes: [], negative_volumes: [], total: 0, negative_total: 0 }
      }
    })
    .catch(() => {})
}

// 加载今日AI摘要
const loadTodaySummary = () => {
  getTodaySummary()
    .then(res => {
      if (res && res.code === 200) {
        todaySummary.value = res.data || null
      }
    })
    .catch(() => {})
}

const goToList = () => uni.switchTab({ url: '/pages/list/list' })

const goToTopicList = () => uni.switchTab({ url: '/pages/list/list' })

const goToTopicDetail = (item) => {
  uni.navigateTo({
    url: `/pages/list/topic?topic_id=${item.topic_id}&topic_name=${encodeURIComponent(item.topic_name || '')}`
  })
}

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

const startPollingStatus = () => {
  if (pollTimer) clearInterval(pollTimer)

  pollTimer = setInterval(() => {
    uni.request({
      url: 'http://127.0.0.1:8008/api/radar_status',
      method: 'GET',
      header: {
        'X-API-Key': 'mr-20260402-6d2d61d53f867e01'
      },
      success: (res) => {
        if (res.data && res.data.code === 200) {
          const statusData = res.data.data

          if (!statusData.is_running && isWaitingForScan.value) {
            isWaitingForScan.value = false
            clearInterval(pollTimer)

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

            loadDashboardData()
          }
        }
      },
      fail: () => {
        clearInterval(pollTimer)
      }
    })
  }, 3000)
}

const startRadar = () => {
  if (isWaitingForScan.value) return

  uni.showLoading({ title: '启动扫描中...' })
  uni.request({
    url: 'http://127.0.0.1:8008/api/start_task',
    method: 'POST',
    header: {
      'X-API-Key': 'mr-20260402-6d2d61d53f867e01'
    },
    success: (res) => {
      uni.hideLoading()
      if (res.data && res.data.code === 200) {
        uni.showToast({ title: '开始全面扫描，请稍候', icon: 'none' })
        isWaitingForScan.value = true
        startPollingStatus()
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

const sysInfo = uni.getSystemInfoSync();
const screenWidth = sysInfo.windowWidth;
const screenHeight = sysInfo.windowHeight;

const fabSizePx = uni.upx2px(120);
const marginPx = uni.upx2px(30);

const fabX = ref(screenWidth - fabSizePx - marginPx);
const fabY = ref(screenHeight - uni.upx2px(260));

let currentX = fabX.value;
let currentY = fabY.value;

const onFabChange = (e) => {
  if (e.detail.source === 'touch') {
    currentX = e.detail.x;
    currentY = e.detail.y;
  }
};

const onFabTouchEnd = () => {
  const isLeftHalf = (currentX + fabSizePx / 2) < (screenWidth / 2);

  if (isLeftHalf) {
    fabX.value = marginPx;
  } else {
    fabX.value = screenWidth - fabSizePx - marginPx;
  }

  fabY.value = currentY;
};

onMounted(() => {
  loadSystemConfig()
  loadDashboardData()
  loadTopics()
  loadVolumeStats()
  loadTodaySummary()
})

</script>

<style scoped>
view, text, scroll-view, button {
  box-sizing: border-box;
}

.page-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #F8FAFC;
  overflow: hidden;
}

.header {
  height: 100rpx;
  background-color: #FFFFFF;
  display: flex;
  align-items: center;
  padding: 0 32rpx;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  z-index: 10;
}

.status-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background-color: #059669;
  margin-right: 16rpx;
}

.header .title {
  font-size: 34rpx;
  font-weight: 600;
  color: #0F172A;
  letter-spacing: 1rpx;
  flex: 1;
}

.header .date {
  font-size: 26rpx;
  color: #64748B;
  font-family: 'JetBrains Mono', monospace;
}

.content-scroll {
  flex: 1;
  height: 0;
  width: 100%;
}

.content-inner {
  padding: 24rpx;
}

.bottom-spacer {
  height: 60rpx;
}

/* Card Base */
.card {
  background-color: #FFFFFF;
  border-radius: 16rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 1rpx 3rpx rgba(0,0,0,0.04);
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #0F172A;
}

.keyword-tag {
  font-size: 22rpx;
  color: #0891B2;
  background: rgba(8, 145, 178, 0.08);
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  font-weight: 500;
  max-width: 280rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Stats Row */
.card-primary .stats-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8rpx 0;
}

.stat-item {
  flex: 1;
  text-align: center;
}

.stat-divider {
  width: 1rpx;
  height: 60rpx;
  background-color: #E2E8F0;
}

.stat-item .number {
  font-size: 52rpx;
  font-weight: 700;
  color: #0F172A;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  line-height: 1.2;
}

.stat-item .label {
  font-size: 24rpx;
  color: #64748B;
  margin-top: 8rpx;
}

.num-danger {
  color: #DC2626 !important;
}

.num-success {
  color: #059669 !important;
}

/* Sentiment Bar */
.sentiment-bar-container {
  margin-top: 8rpx;
}

.sentiment-bar {
  height: 8rpx;
  border-radius: 4rpx;
  display: flex;
  overflow: hidden;
  background: #E2E8F0;
}

.bar-segment {
  transition: width 0.5s ease;
}

.bar-segment.positive {
  background-color: #059669;
}

.bar-segment.neutral {
  background-color: #D97706;
}

.bar-segment.negative {
  background-color: #DC2626;
}

.sentiment-legend {
  display: flex;
  justify-content: space-between;
  margin-top: 20rpx;
}

.legend-item {
  display: flex;
  align-items: center;
}

.legend-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  margin-right: 8rpx;
}

.legend-dot.positive {
  background-color: #059669;
}

.legend-dot.neutral {
  background-color: #D97706;
}

.legend-dot.negative {
  background-color: #DC2626;
}

.legend-label {
  font-size: 24rpx;
  color: #64748B;
  margin-right: 8rpx;
}

.legend-value {
  font-size: 24rpx;
  color: #0F172A;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}

/* Summary */
.summary-text {
  font-size: 28rpx;
  line-height: 1.7;
  color: #475569;
}

.highlight {
  font-weight: 600;
  color: #0F172A;
}

/* Alert Box */
.alert-box {
  display: flex;
  align-items: flex-start;
  padding: 20rpx;
  border-radius: 12rpx;
  margin-top: 20rpx;
}

.alert-danger {
  background-color: #FEF2F2;
}

.alert-safe {
  background-color: #F0FDF4;
}

.alert-indicator {
  width: 4rpx;
  height: 100%;
  min-height: 60rpx;
  border-radius: 2rpx;
  margin-right: 16rpx;
}

.alert-danger .alert-indicator {
  background-color: #DC2626;
}

.alert-safe .alert-indicator {
  background-color: #059669;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-size: 28rpx;
  font-weight: 600;
  display: block;
  margin-bottom: 4rpx;
}

.alert-danger .alert-title {
  color: #991B1B;
}

.alert-safe .alert-title {
  color: #065F46;
}

.alert-desc {
  font-size: 24rpx;
  line-height: 1.5;
}

.alert-danger .alert-desc {
  color: #B91C1C;
}

.alert-safe .alert-desc {
  color: #047857;
}

/* Latest Alert */
.latest-alert {
  margin-top: 16rpx;
  padding: 20rpx;
  background-color: #F8FAFC;
  border-radius: 12rpx;
  border: 1px solid #E2E8F0;
}

.alert-meta {
  display: flex;
  align-items: center;
  margin-bottom: 12rpx;
}

.platform-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  margin-right: 8rpx;
}

.platform-dot.wb { background-color: #FF8200; }
.platform-dot.xhs { background-color: #FF2442; }
.platform-dot.bili { background-color: #FB7299; }
.platform-dot.zhihu { background-color: #0066FF; }
.platform-dot.dy { background-color: #1C1C1E; }
.platform-dot.ks { background-color: #FF5000; }
.platform-dot.tieba { background-color: #3388FF; }

.platform-name {
  font-size: 24rpx;
  color: #64748B;
  font-weight: 500;
}

.dot-sep {
  margin: 0 10rpx;
  color: #CBD5E1;
}

.alert-time {
  font-size: 24rpx;
  color: #94A3B8;
  font-family: 'JetBrains Mono', monospace;
}

.alert-report {
  font-size: 28rpx;
  color: #334155;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.alert-action {
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #0891B2;
  font-weight: 500;
}

.arrow {
  margin-left: 4rpx;
}

/* 话题热度榜 */
.more-link {
  font-size: 26rpx;
  color: #0891B2;
  font-weight: 500;
}

.topic-rank-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.topic-rank-item {
  display: flex;
  align-items: center;
  padding: 18rpx 0;
  border-bottom: 1rpx solid #F1F5F9;
}
.topic-rank-item:last-child {
  border-bottom: none;
}

.rank-num {
  width: 40rpx;
  font-size: 28rpx;
  font-weight: 700;
  color: #CBD5E1;
  font-family: 'JetBrains Mono', monospace;
  text-align: center;
  flex-shrink: 0;
}
.rank-num.top {
  color: #DC2626;
}

.rank-content {
  flex: 1;
  overflow: hidden;
  margin-left: 12rpx;
}

.rank-title-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.risk-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  flex-shrink: 0;
}
.risk-dot.negative { background-color: #DC2626; }
.risk-dot.neutral { background-color: #D97706; }
.risk-dot.positive { background-color: #059669; }

.rank-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #0F172A;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-meta {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 6rpx;
}

.rank-platforms {
  font-size: 22rpx;
  color: #94A3B8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 280rpx;
}

.rank-count {
  font-size: 22rpx;
  color: #64748B;
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
}

.rank-arrow {
  font-size: 36rpx;
  color: #CBD5E1;
  flex-shrink: 0;
  margin-left: 8rpx;
}

/* 今日摘要 - 话题标签 */
.topic-pills {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 16rpx;
  flex-wrap: wrap;
}

.topic-pill-label {
  font-size: 22rpx;
  color: #64748B;
  font-weight: 500;
}

.topic-pill {
  font-size: 24rpx;
  color: #DC2626;
  background-color: #FEF2F2;
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
  font-weight: 500;
}

.escalating-list {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-top: 10rpx;
  flex-wrap: wrap;
}

.escalating-label {
  font-size: 22rpx;
  color: #64748B;
}

.escalating-item {
  font-size: 22rpx;
  color: #B91C1C;
  background-color: #FFF7F7;
  padding: 3rpx 12rpx;
  border-radius: 6rpx;
  border: 1rpx solid #FEE2E2;
}

/* 7日声量趋势图 */
.trend-chart {
  padding: 8rpx 0;
}

.trend-legend {
  display: flex;
  gap: 24rpx;
  margin-bottom: 16rpx;
}

.trend-legend .legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.legend-bar {
  width: 20rpx;
  height: 8rpx;
  border-radius: 4rpx;
}
.total-bar {
  background-color: #0F172A;
}
.neg-bar {
  background-color: #DC2626;
}

.trend-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 160rpx;
  padding: 0 4rpx;
}

.bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 6rpx;
}

.bar-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 2rpx;
  height: 140rpx;
}

.bar {
  width: 24rpx;
  border-radius: 3rpx 3rpx 0 0;
  min-height: 4rpx;
}
.bar.total-bar {
  background: linear-gradient(to top, #334155, #0F172A);
}
.bar.neg-bar {
  background: linear-gradient(to top, #F87171, #DC2626);
}

.bar-label {
  font-size: 20rpx;
  color: #94A3B8;
  font-family: 'JetBrains Mono', monospace;
}

/* Chart Placeholder */
.chart-placeholder {
  height: 200rpx;
  background-color: #F8FAFC;
  border-radius: 12rpx;
  border: 1px dashed #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-text {
  font-size: 26rpx;
  color: #94A3B8;
}

/* Primary Button */
.action-container {
  padding: 8rpx 0;
}

.primary-btn {
  width: 100%;
  padding: 26rpx 0;
  background-color: #0F172A;
  border-radius: 12rpx;
  color: #FFFFFF;
  font-size: 30rpx;
  font-weight: 500;
  display: flex;
  justify-content: center;
  align-items: center;
  border: none;
  margin: 0;
}

.primary-btn:active {
  background-color: #1E293B;
}

/* FAB */
.fab-area {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  pointer-events: none;
}

.agent-fab-view {
  width: 120rpx;
  height: 120rpx;
  pointer-events: auto;
}

.agent-fab {
  width: 100%;
  height: 100%;
  background-color: #0F172A;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.3);
}

.agent-fab:active {
  transform: scale(0.92);
}

.fab-text {
  color: #FFFFFF;
  font-size: 40rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
}
</style>
