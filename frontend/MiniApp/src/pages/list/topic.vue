<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">‹</view>
      <view class="title">话题详情</view>
    </view>

    <scroll-view scroll-y class="content" v-if="topicData.topic_id">
      <!-- Header: 话题名称 + 风险标签 -->
      <view class="topic-header-card">
        <view class="topic-title-row">
          <text class="topic-name">{{ topicData.topic_name || '未知话题' }}</text>
          <view class="sentiment-tag" :class="topicData.risk_class">
            <view class="sentiment-dot"></view>
            {{ topicData.sentiment }}
          </view>
        </view>
        <view class="signal-tag" :class="getSignalClass(topicData.evolution_signal)" v-if="topicData.evolution_signal !== 'unknown'">
          {{ getSignalText(topicData.evolution_signal) }}
        </view>
      </view>

      <!-- AI 话题摘要卡片 -->
      <view class="detail-card ai-card" v-if="topicData.cluster_summary">
        <view class="card-label">📊 AI 话题摘要</view>
        <text class="ai-summary-text" user-select="true">{{ topicData.cluster_summary }}</text>
      </view>

      <!-- 话题基本信息卡片 -->
      <view class="detail-card info-card">
        <view class="info-row">
          <view class="info-label">关联监控词</view>
          <view class="info-value keyword-hl">{{ topicData.keyword || '未知' }}</view>
        </view>
        <view class="info-row">
          <view class="info-label">涉及平台</view>
          <view class="info-value platforms-value">
            <view
              class="plat-badge"
              v-for="(plat, idx) in topicData.platforms"
              :key="idx"
              :class="getPlatClass(plat)"
            >{{ plat }}</view>
          </view>
        </view>
        <view class="info-row">
          <view class="info-label">情感判断</view>
          <view class="info-value" :class="topicData.risk_class">
            {{ topicData.sentiment }} (系统分析)
          </view>
        </view>
        <view class="info-row">
          <view class="info-label">预警级别</view>
          <view class="info-value" :class="topicData.risk_class === 'negative' ? 'negative' : 'unprocessed'">
            {{ topicData.risk_class === 'negative' ? '🚨 高风险预警' : '✅ 常规提示' }}
          </view>
        </view>
        <view class="info-row">
          <view class="info-label">累计帖子</view>
          <view class="info-value">{{ topicData.post_count || 0 }} 条</view>
        </view>
        <view class="info-row">
          <view class="info-label">首次发现</view>
          <view class="info-value">{{ topicData.first_seen || '未知' }}</view>
        </view>
        <view class="info-row">
          <view class="info-label">最近更新</view>
          <view class="info-value">{{ topicData.last_seen || '未知' }}</view>
        </view>
      </view>

      <!-- 话题演化追踪卡片 -->
      <view class="detail-card evolution-card"
        v-if="topicData.evolution_timeline && topicData.evolution_timeline.length">
        <view class="evolution-header">
          <text class="card-label">📈 话题演化追踪</text>
          <view class="risk-path" v-if="riskPath">
            <text class="path-label">风险演变：</text>
            <text class="path-value">{{ riskPath }}</text>
          </view>
        </view>

        <view class="timeline">
          <view
            class="timeline-item"
            v-for="(item, idx) in topicData.evolution_timeline"
            :key="idx"
            :class="{ 'is-current': item.is_current }"
          >
            <view class="timeline-dot"></view>
            <view class="timeline-content">
              <view class="timeline-header">
                <text class="timeline-time">{{ item.scan_time || '未知时间' }}</text>
                <text class="timeline-risk" :class="getRiskClass(item.risk_level)">
                  风险{{ item.risk_level }}
                </text>
                <text class="timeline-current-tag" v-if="item.is_current">当前</text>
              </view>
              <text class="timeline-issue">{{ item.core_issue || '无' }}</text>
              <text class="timeline-platforms" v-if="item.platforms && item.platforms.length">
                {{ formatPlatforms(item.platforms) }} · {{ item.post_count || 1 }}条帖子
              </text>
            </view>
          </view>
        </view>
      </view>

      <!-- 关联帖子列表 -->
      <view class="section-title">📋 相关帖子 ({{ (topicData.posts || []).length }})</view>

      <view
        class="post-card"
        v-for="(post, idx) in topicData.posts"
        :key="idx"
        @click="goToDetail(post)"
      >
        <view class="post-header">
          <view class="platform-info">
            <view class="platform-dot" :class="post.platform"></view>
            <text class="platform-name">{{ post.platform_name || post.platform }}</text>
          </view>
          <view class="sentiment-tag small" :class="post.sentiment">
            <view class="sentiment-dot"></view>
            {{ post.risk_text }}
          </view>
        </view>
        <view class="post-content">
          <text v-if="post.core_issue && post.core_issue !== '无异常'" class="core-issue">【{{post.core_issue}}】</text>
          {{ post.content || post.title }}
        </view>
        <view class="post-footer">
          <text class="post-time">{{ post.publish_time ? post.publish_time.substring(5, 16) : '' }}</text>
          <text class="post-action">查看详情 →</text>
        </view>
      </view>

      <view v-if="(topicData.posts || []).length === 0" class="empty-posts">
        <text>暂无关联帖子</text>
      </view>

      <!-- 底部操作 -->
      <view class="detail-actions">
        <view class="detail-btn secondary" @click="openOriginalUrl">复制话题链接</view>
        <view
          class="detail-btn primary"
          :class="{ 'disabled': topicData.is_processed === 1 }"
          @click="markAsProcessed"
        >
          {{ topicData.is_processed === 1 ? '已被标记处理' : '标记为已处理' }}
        </view>
      </view>

      <view class="bottom-spacer"></view>
    </scroll-view>

    <!-- 加载中 -->
    <view class="loading-state" v-else-if="loading">
      <text>加载中...</text>
    </view>

    <!-- 空状态 -->
    <view class="loading-state" v-else>
      <text>话题不存在或已被删除</text>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getTopicDetail, markTopicProcessed } from '../../utils/api.js'

const topicData = ref({})
const loading = ref(true)

onLoad((options) => {
  if (options.topic_id) {
    fetchTopicDetail(options.topic_id)
  }
})

const goBack = () => uni.navigateBack()

const fetchTopicDetail = (topicId) => {
  uni.showLoading({ title: '加载中...' })
  loading.value = true
  getTopicDetail(topicId)
    .then((res) => {
      uni.hideLoading()
      loading.value = false
      if (res && res.code === 200 && res.data) {
        topicData.value = res.data
      }
    })
    .catch(() => {
      uni.hideLoading()
      loading.value = false
      uni.showToast({ title: '加载失败', icon: 'none' })
    })
}

const goToDetail = (post) => {
  // 复用 detail.vue 的跳转逻辑，传递完整数据
  uni.navigateTo({
    url: `/pages/list/detail?data=${encodeURIComponent(JSON.stringify(post))}`
  })
}

const markAsProcessed = () => {
  if (topicData.value.is_processed === 1) return
  const topicId = topicData.value.topic_id
  if (!topicId) return
  markTopicProcessed(topicId)
    .then(() => {
      topicData.value.is_processed = 1
      uni.showToast({ title: '已标记处理', icon: 'success' })
    })
    .catch(() => {
      uni.showToast({ title: '操作失败', icon: 'none' })
    })
}

const openOriginalUrl = () => {
  // 话题没有单一链接，取第一个帖子的链接
  const firstPost = (topicData.value.posts || [])[0]
  if (firstPost && firstPost.url) {
    uni.setClipboardData({
      data: firstPost.url,
      success: () => {
        uni.showToast({ title: '链接已复制，请在浏览器打开', icon: 'none' })
      }
    })
  } else {
    uni.showToast({ title: '暂无可用链接', icon: 'none' })
  }
}

// 演化信号样式
const getSignalClass = (signal) => {
  const map = { 'escalating': 'signal-red', 'stable': 'signal-yellow', 'deescalating': 'signal-green' }
  return map[signal] || 'signal-gray'
}

const getSignalText = (signal) => {
  const map = { 'escalating': '⚠️ 风险升级', 'stable': '→ 趋于稳定', 'deescalating': '↓ 风险缓和' }
  return map[signal] || '未知'
}

// 风险等级样式
const getRiskClass = (level) => {
  const lvl = parseInt(level) || 0
  if (lvl >= 4) return 'risk-high'
  if (lvl >= 3) return 'risk-medium'
  return 'risk-low'
}

// 平台小圆点颜色
const getPlatClass = (platName) => {
  const map = { '微博': 'wb', '小红书': 'xhs', 'B站': 'bili', '知乎': 'zhihu', '抖音': 'dy', '快手': 'ks', '贴吧': 'tieba' }
  return map[platName] || ''
}

// 平台列表文字
const formatPlatforms = (platforms) => {
  if (!platforms || !platforms.length) return ''
  return platforms.join('、')
}

// 风险演变路径
const riskPath = computed(() => {
  const tl = topicData.value.evolution_timeline || []
  if (tl.length < 2) return ''
  return tl.map(item => item.risk_level || '?').join(' → ')
})
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #f5f5f5; }

.header {
  height: 100rpx; background-color: #ffffff; display: flex; justify-content: center; align-items: center;
  border-bottom: 2rpx solid #eee; z-index: 10; position: relative; flex-shrink: 0;
}
.header .title { font-size: 36rpx; font-weight: 600; color: #333; }
.header .back-btn { position: absolute; left: 32rpx; top: 50%; transform: translateY(-50%); font-size: 56rpx; color: #333; font-weight: 300; padding: 10rpx; }

.content { flex: 1; overflow-y: auto; padding: 32rpx; box-sizing: border-box; }
.bottom-spacer { height: 60rpx; }
.loading-state { flex: 1; display: flex; align-items: center; justify-content: center; color: #999; font-size: 28rpx; }

/* 话题头部卡片 */
.topic-header-card {
  background-color: #fff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.03);
  border-left: 6rpx solid #667eea;
}

.topic-title-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.topic-name {
  font-size: 36rpx;
  font-weight: 700;
  color: #0F172A;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.signal-tag {
  font-size: 22rpx;
  font-weight: 600;
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  flex-shrink: 0;
}

.signal-red { background-color: #fff2f0; color: #ff4d4f; }
.signal-yellow { background-color: #fffbe6; color: #faad14; }
.signal-green { background-color: #f6ffed; color: #52c41a; }
.signal-gray { background-color: #f5f5f5; color: #999; }

/* 统一卡片 */
.detail-card {
  background-color: #fff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.03);
}

.card-label {
  font-size: 28rpx;
  font-weight: 700;
  color: #333;
  margin-bottom: 16rpx;
}

/* AI 汇总卡片 */
.ai-card { border-left: 6rpx solid #667eea; }
.ai-summary-text {
  font-size: 28rpx; line-height: 1.8; color: #334155;
  display: block; white-space: pre-wrap; word-break: break-all;
}
.report-section { margin-top: 20rpx; }
.report-divider { height: 2rpx; background: #f0f0f0; margin-bottom: 20rpx; }
.report-text {
  font-size: 28rpx; line-height: 1.8; color: #333;
  display: block; white-space: pre-wrap; word-break: break-all;
}

/* 信息卡片 */
.info-card .info-row { display: flex; justify-content: space-between; align-items: center; padding: 20rpx 0; border-bottom: 2rpx solid #fafafa; }
.info-card .info-row:last-child { border-bottom: none; padding-bottom: 0; }
.info-card .info-row:first-child { padding-top: 0; }
.info-label { font-size: 28rpx; color: #999; }
.info-value { font-size: 28rpx; color: #333; font-weight: 500; }
.keyword-hl { color: #667eea; font-weight: bold; }
.negative { color: #ff4d4f; }
.unprocessed { color: #faad14; }

.platforms-value { display: flex; flex-wrap: wrap; gap: 8rpx; justify-content: flex-end; }
.plat-badge {
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  font-size: 22rpx;
  background-color: #f0f0f5;
  color: #666;
}
.plat-badge.wb { background-color: #fff0e0; color: #FF8200; }
.plat-badge.xhs { background-color: #fff0f0; color: #FF2442; }
.plat-badge.bili { background-color: #fff0f5; color: #FB7299; }
.plat-badge.zhihu { background-color: #eef4ff; color: #0066FF; }
.plat-badge.dy { background-color: #f5f5f5; color: #1C1C1E; }
.plat-badge.ks { background-color: #fff4f0; color: #FF5000; }
.plat-badge.tieba { background-color: #eef4ff; color: #3388FF; }

/* 演化卡片 */
.evolution-card { border-left: 6rpx solid #667eea; }

.evolution-header {
  margin-bottom: 20rpx;
}

.risk-path {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 12rpx;
  padding: 12rpx 16rpx;
  background-color: #f8f8fc;
  border-radius: 12rpx;
}
.path-label { font-size: 24rpx; color: #999; }
.path-value { font-size: 28rpx; font-weight: 700; color: #667eea; letter-spacing: 2rpx; }

/* 时间线 */
.timeline { position: relative; padding-left: 32rpx; }
.timeline::before {
  content: ''; position: absolute; left: 8rpx; top: 12rpx; bottom: 12rpx;
  width: 2rpx; background-color: #e8e8f0;
}

.timeline-item { position: relative; padding-bottom: 32rpx; padding-left: 24rpx; }
.timeline-item:last-child { padding-bottom: 0; }
.timeline-item.is-current .timeline-dot { background-color: #667eea; width: 16rpx; height: 16rpx; margin-left: -2rpx; }

.timeline-dot {
  position: absolute; left: -28rpx; top: 8rpx;
  width: 12rpx; height: 12rpx; border-radius: 50%;
  background-color: #ccc; border: 2rpx solid #fff;
}

.timeline-content { background-color: #fafafa; border-radius: 12rpx; padding: 16rpx 20rpx; }
.timeline-header { display: flex; align-items: center; gap: 12rpx; margin-bottom: 8rpx; }
.timeline-time { font-size: 24rpx; color: #999; }
.timeline-risk { font-size: 24rpx; font-weight: 600; }
.risk-high { color: #ff4d4f; }
.risk-medium { color: #faad14; }
.risk-low { color: #52c41a; }
.timeline-current-tag { font-size: 20rpx; background-color: #667eea; color: #fff; padding: 2rpx 8rpx; border-radius: 8rpx; }
.timeline-issue { display: block; font-size: 28rpx; color: #333; font-weight: 500; margin-bottom: 6rpx; }
.timeline-platforms { font-size: 24rpx; color: #999; }

/* 关联帖子列表标题 */
.section-title {
  font-size: 30rpx;
  font-weight: 700;
  color: #333;
  margin-bottom: 16rpx;
  margin-top: 8rpx;
}

/* 帖子卡片 */
.post-card {
  background-color: #fff;
  border-radius: 14rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 1rpx 3rpx rgba(0,0,0,0.04);
  position: relative;
}

.post-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 6rpx; border-radius: 3rpx 0 0 3rpx;
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14rpx;
}

.platform-info { display: flex; align-items: center; }
.platform-dot { width: 8rpx; height: 8rpx; border-radius: 50%; margin-right: 10rpx; }
.platform-dot.wb { background-color: #FF8200; }
.platform-dot.xhs { background-color: #FF2442; }
.platform-dot.bili { background-color: #FB7299; }
.platform-dot.zhihu { background-color: #0066FF; }
.platform-dot.dy { background-color: #1C1C1E; }
.platform-dot.ks { background-color: #FF5000; }
.platform-dot.tieba { background-color: #3388FF; }

.platform-name { font-size: 26rpx; font-weight: 500; color: #475569; }

.sentiment-tag {
  display: flex; align-items: center; padding: 6rpx 14rpx;
  border-radius: 6rpx; font-size: 22rpx; font-weight: 500;
}
.sentiment-tag.small { padding: 4rpx 10rpx; font-size: 20rpx; }
.sentiment-dot { width: 6rpx; height: 6rpx; border-radius: 50%; margin-right: 8rpx; }
.sentiment-tag.negative { background-color: #FEF2F2; color: #DC2626; }
.sentiment-tag.negative .sentiment-dot { background-color: #DC2626; }
.sentiment-tag.positive { background-color: #F0FDF4; color: #059669; }
.sentiment-tag.positive .sentiment-dot { background-color: #059669; }
.sentiment-tag.neutral { background-color: #FFFBEB; color: #D97706; }
.sentiment-tag.neutral .sentiment-dot { background-color: #D97706; }

.post-content {
  font-size: 26rpx; color: #334155; line-height: 1.6;
  margin-bottom: 16rpx;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
.core-issue { font-weight: 600; color: #0F172A; }

.post-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 14rpx;
  border-top: 1rpx solid #F1F5F9;
}
.post-time { font-size: 22rpx; color: #94A3B8; font-family: 'JetBrains Mono', monospace; }
.post-action { font-size: 26rpx; font-weight: 500; color: #0891B2; }

.empty-posts { text-align: center; padding: 60rpx; color: #94A3B8; font-size: 28rpx; }

/* 底部操作 */
.detail-actions { display: flex; gap: 24rpx; margin-top: 16rpx; padding-bottom: 20rpx; }
.detail-btn {
  flex: 1; padding: 26rpx; border-radius: 20rpx;
  font-size: 30rpx; font-weight: 600; text-align: center; transition: opacity 0.2s;
}
.detail-btn:active { opacity: 0.8; }
.detail-btn.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff; box-shadow: 0 8rpx 20rpx rgba(102, 126, 234, 0.3);
}
.detail-btn.primary.disabled { background: #e8e8e8; color: #999; box-shadow: none; pointer-events: none; }
.detail-btn.secondary { background-color: #fff; color: #667eea; border: 2rpx solid #667eea; }
</style>
