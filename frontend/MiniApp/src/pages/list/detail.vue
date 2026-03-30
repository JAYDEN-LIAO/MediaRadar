<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">‹</view>
      <view class="title">舆情详情</view>
    </view>
    
    <scroll-view scroll-y class="content">
      <view class="detail-card source-card">
        <view class="platform-info">
          <text class="platform-icon" :class="itemData.platform">{{ getPlatformEmoji(itemData.platform) }}</text>
          <text class="name">{{ getPlatformName(itemData.platform) }}</text>
        </view>
        <view class="sentiment-tag" :class="itemData.riskClass">{{ itemData.riskText }}</view>
      </view>
      
      <view class="detail-card content-card">
        <text class="full-text" user-select="true">{{ itemData.report || '暂无详细内容' }}</text>
        
        <view class="image-gallery" v-if="itemData.image_urls && itemData.image_urls.length > 0">
          <image 
            class="gallery-img" 
            v-for="(img, idx) in itemData.image_urls" 
            :key="idx" 
            :src="img" 
            mode="aspectFill"
            @click="previewImage(img, itemData.image_urls)"
          />
        </view>

        <view class="tags" v-if="itemData.core_issue && itemData.core_issue !== '无异常'">
          <view class="tag"><text class="hash">#</text>{{ itemData.core_issue }}</view>
        </view>
      </view>
      
      <view class="detail-card info-card">
        <view class="info-row">
          <view class="info-label">关联监控词</view>
          <view class="info-value keyword-hl">{{ itemData.keyword || '未知' }}</view>
        </view>
        <view class="info-row">
          <view class="info-label">发布时间</view>
          <view class="info-value">{{ itemData.create_time || '刚刚' }}</view>
        </view>
        <view class="info-row">
          <view class="info-label">情感判断</view>
          <view class="info-value" :class="itemData.riskClass">
            {{ itemData.riskText }} (系统分析)
          </view>
        </view>
        <view class="info-row">
          <view class="info-label">预警级别</view>
          <view class="info-value" :class="itemData.riskClass === 'negative' ? 'negative' : 'unprocessed'">
            {{ itemData.riskClass === 'negative' ? '🚨 高风险预警' : '✅ 常规提示' }}
          </view>
        </view>
      </view>

      <!-- 话题追踪卡片（仅话题有历史记录时显示） -->
      <view class="detail-card evolution-card" v-if="topicEvolution && !topicEvolution.is_new_topic">
        <view class="evolution-header">
          <text class="evolution-title">📊 话题追踪</text>
          <text class="evolution-signal" :class="getSignalClass(topicEvolution.evolution_signal)">
            {{ getSignalText(topicEvolution.evolution_signal) }}
          </text>
        </view>

        <view class="evolution-summary">
          <text class="summary-text">
            该话题最早发现于 {{ topicEvolution.duration_days }} 天前，
            已连续追踪 {{ topicEvolution.total_scan_count }} 次，
            累计影响 {{ topicEvolution.total_post_count }} 条帖子
          </text>
        </view>

        <!-- 风险演变路径 -->
        <view class="risk-path" v-if="topicEvolution.risk_evolution_path">
          <text class="path-label">风险演变：</text>
          <text class="path-value">{{ topicEvolution.risk_evolution_path }}</text>
        </view>

        <!-- 时间线 -->
        <view class="timeline" v-if="topicEvolution.timeline && topicEvolution.timeline.length">
          <view
            class="timeline-item"
            v-for="(item, idx) in topicEvolution.timeline"
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
      
      <view class="detail-actions">
        <view class="detail-btn secondary" @click="openOriginalUrl">复制原文链接</view>
        <view 
          class="detail-btn primary" 
          :class="{'disabled': itemData.is_processed === 1}"
          @click="markAsProcessed"
        >
          {{ itemData.is_processed === 1 ? '已被标记处理' : '标记为已处理' }}
        </view>
      </view>
      <view class="bottom-spacer"></view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

// 核心数据源（完全保留原逻辑）
const itemData = ref({})
// 话题演化追踪数据
const topicEvolution = ref(null)

onLoad((options) => {
  if (options.data) {
    try {
      itemData.value = JSON.parse(decodeURIComponent(options.data))
    } catch (e) {
      console.error('解析详情数据失败', e)
    }
  }
  // 解析成功后加载话题演化追踪数据
  if (itemData.value && itemData.value.keyword) {
    loadTopicEvolution()
  }
})

const goBack = () => uni.navigateBack()

// 完善的平台图标字典（对接你 list.vue 的设定）
const getPlatformEmoji = (p) => {
  const map = { 'wb': '📘', 'xhs': '📕', 'dy': '🎵', 'bili': '📺', 'ks': '📷', 'toutiao': '📰', 'zhihu': '🎓', 'tieba': '💬' }
  return map[p] || '🌐'
}

const getPlatformName = (p) => {
  const map = { 'wb': '微博', 'xhs': '小红书', 'dy': '抖音', 'bili': 'B站', 'ks': '快手', 'toutiao': '今日头条', 'zhihu': '知乎', 'tieba': '贴吧' }
  return map[p] || p || '未知平台'
}

// 图片预览原生地接口
const previewImage = (currentUrl, allUrls) => {
  uni.previewImage({
    current: currentUrl,
    urls: allUrls
  })
}

// 跳转/复制外链（完全保留原逻辑）
const openOriginalUrl = () => {
  if (itemData.value.url) {
    uni.setClipboardData({
      data: itemData.value.url,
      success: () => {
        uni.showToast({ title: '原链接已复制，请在浏览器中打开', icon: 'none' })
      }
    })
  } else {
    uni.showToast({ title: '未获取到原文链接', icon: 'none' })
  }
}

// 标记处理（保留你的 mock 或对接未来的真实 API）
const markAsProcessed = () => {
  if (itemData.value.is_processed === 1) return // 如果已处理直接跳过
  uni.showToast({ title: '已标记处理', icon: 'success' })
  setTimeout(() => goBack(), 1000)
}

// ============================================================
// 话题演化追踪
// ============================================================
const loadTopicEvolution = () => {
  const keyword = itemData.value.keyword || ''
  const topicId = itemData.value.topic_id || ''

  uni.request({
    url: 'http://127.0.0.1:8008/api/topic_evolution',
    data: { keyword, topic_id: topicId },
    method: 'GET',
    success: (res) => {
      if (res.data && res.data.code === 200 && res.data.data) {
        const data = res.data.data
        if (!data.is_new_topic && data.evolution) {
          topicEvolution.value = data.evolution
        }
      }
    },
    fail: () => {
      console.log('话题演化数据加载失败')
    }
  })
}

// 辅助：信号样式
const getSignalClass = (signal) => {
  const map = {
    'escalating': 'signal-red',
    'stable': 'signal-yellow',
    'deescalating': 'signal-green'
  }
  return map[signal] || 'signal-gray'
}

// 辅助：信号文本
const getSignalText = (signal) => {
  const map = {
    'escalating': '⚠️ 风险升级',
    'stable': '→ 趋于稳定',
    'deescalating': '↓ 风险缓和'
  }
  return map[signal] || '未知'
}

// 辅助：风险等级样式
const getRiskClass = (level) => {
  const lvl = parseInt(level) || 0
  if (lvl >= 4) return 'risk-high'
  if (lvl >= 3) return 'risk-medium'
  return 'risk-low'
}

// 辅助：平台列表文字
const formatPlatforms = (platforms) => {
  if (!platforms || !platforms.length) return ''
  const nameMap = { 'wb': '微博', 'xhs': '小红书', 'dy': '抖音', 'bili': 'B站', 'ks': '快手', 'zhihu': '知乎', 'tieba': '贴吧' }
  return platforms.map(p => nameMap[p] || p).join('、')
}
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #f5f5f5; }

/* 统一 Header：去掉了右上角多余按钮，纯绝对定位居中，防畸形 */
.header { 
  height: 100rpx; background-color: #ffffff; display: flex; justify-content: center; align-items: center; 
  border-bottom: 2rpx solid #eee; z-index: 10; position: relative; flex-shrink: 0;
}
.header .title { font-size: 36rpx; font-weight: 600; color: #333; }
.header .back-btn { position: absolute; left: 32rpx; top: 50%; transform: translateY(-50%); font-size: 56rpx; color: #333; font-weight: 300; padding: 10rpx;}

.content { flex: 1; overflow-y: auto; padding: 32rpx; box-sizing: border-box; }
.bottom-spacer { height: 60rpx; }

/* 统一卡片基础样式：大圆角，柔和阴影 */
.detail-card { background-color: #fff; border-radius: 24rpx; padding: 32rpx; margin-bottom: 24rpx; box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.03); }

/* 第一部分：来源与情感 */
.source-card { display: flex; align-items: center; justify-content: space-between; }
.platform-info { display: flex; align-items: center; gap: 16rpx; }
.platform-icon { font-size: 48rpx; }
.platform-info .name { font-size: 32rpx; font-weight: 600; color: #333; }

.sentiment-tag { padding: 8rpx 24rpx; border-radius: 24rpx; font-size: 26rpx; font-weight: 600; }
.sentiment-tag.negative { background-color: #fff2f0; color: #ff4d4f; }
.sentiment-tag.positive { background-color: #f6ffed; color: #52c41a; }
.sentiment-tag.neutral { background-color: #fffbe6; color: #faad14; }

/* 第二部分：核心内容（字数全开） */
.content-card .full-text { 
  font-size: 30rpx; line-height: 1.8; color: #333; 
  display: block; white-space: pre-wrap; word-break: break-all; 
}

/* 预留图片九宫格排版 */
.image-gallery { display: flex; flex-wrap: wrap; gap: 16rpx; margin-top: 32rpx; }
.gallery-img { width: calc((100% - 32rpx) / 3); aspect-ratio: 1/1; border-radius: 12rpx; background-color: #f0f0f0; }

.content-card .tags { margin-top: 32rpx; padding-top: 24rpx; border-top: 2rpx dashed #eee; }
.content-card .tag { display: inline-flex; align-items: center; padding: 10rpx 24rpx; background-color: #f5f5f5; border-radius: 30rpx; font-size: 26rpx; color: #666; font-weight: 500;}
.content-card .tag .hash { color: #667eea; margin-right: 6rpx; font-weight: bold;}

/* 第三部分：AI 分析信息 */
.info-card .info-row { display: flex; justify-content: space-between; align-items: center; padding: 24rpx 0; border-bottom: 2rpx solid #fafafa; }
.info-card .info-row:last-child { border-bottom: none; padding-bottom: 0;}
.info-card .info-row:first-child { padding-top: 0;}
.info-card .info-label { font-size: 28rpx; color: #999; }
.info-card .info-value { font-size: 28rpx; color: #333; font-weight: 500;}
.info-card .keyword-hl { color: #667eea; font-weight: bold;}
.info-card .info-value.negative { color: #ff4d4f; }
.info-card .info-value.unprocessed { color: #faad14; }

/* 底部操作区 */
.detail-actions { display: flex; gap: 24rpx; margin-top: 16rpx; padding-bottom: 20rpx;}
.detail-btn { flex: 1; padding: 26rpx; border-radius: 20rpx; font-size: 30rpx; font-weight: 600; text-align: center; transition: opacity 0.2s;}
.detail-btn:active { opacity: 0.8; }
.detail-btn.primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; box-shadow: 0 8rpx 20rpx rgba(102, 126, 234, 0.3);}
.detail-btn.primary.disabled { background: #e8e8e8; color: #999; box-shadow: none; pointer-events: none;}
.detail-btn.secondary { background-color: #fff; color: #667eea; border: 2rpx solid #667eea; }

/* ============================================================
   话题追踪卡片
   ============================================================ */
.evolution-card {
  border-left: 6rpx solid #667eea;
}

.evolution-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.evolution-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #333;
}

.evolution-signal {
  font-size: 26rpx;
  font-weight: 600;
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
}

.signal-red { background-color: #fff2f0; color: #ff4d4f; }
.signal-yellow { background-color: #fffbe6; color: #faad14; }
.signal-green { background-color: #f6ffed; color: #52c41a; }
.signal-gray { background-color: #f5f5f5; color: #999; }

.evolution-summary {
  font-size: 28rpx;
  color: #666;
  line-height: 1.6;
  margin-bottom: 20rpx;
}

.risk-path {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
  padding: 16rpx;
  background-color: #f8f8fc;
  border-radius: 12rpx;
}

.path-label { font-size: 26rpx; color: #999; }
.path-value { font-size: 30rpx; font-weight: 700; color: #667eea; letter-spacing: 2rpx; }

/* 时间线 */
.timeline {
  position: relative;
  padding-left: 32rpx;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 8rpx;
  top: 12rpx;
  bottom: 12rpx;
  width: 2rpx;
  background-color: #e8e8f0;
}

.timeline-item {
  position: relative;
  padding-bottom: 32rpx;
  padding-left: 24rpx;
}

.timeline-item:last-child { padding-bottom: 0; }

.timeline-item.is-current .timeline-dot {
  background-color: #667eea;
  width: 16rpx;
  height: 16rpx;
  margin-left: -2rpx;
}

.timeline-dot {
  position: absolute;
  left: -28rpx;
  top: 8rpx;
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background-color: #ccc;
  border: 2rpx solid #fff;
}

.timeline-content {
  background-color: #fafafa;
  border-radius: 12rpx;
  padding: 16rpx 20rpx;
}

.timeline-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.timeline-time { font-size: 24rpx; color: #999; }

.timeline-risk {
  font-size: 24rpx;
  font-weight: 600;
}

.timeline-risk.risk-high { color: #ff4d4f; }
.timeline-risk.risk-medium { color: #faad14; }
.timeline-risk.risk-low { color: #52c41a; }

.timeline-current-tag {
  font-size: 20rpx;
  background-color: #667eea;
  color: #fff;
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
}

.timeline-issue {
  display: block;
  font-size: 28rpx;
  color: #333;
  font-weight: 500;
  margin-bottom: 6rpx;
}

.timeline-platforms {
  font-size: 24rpx;
  color: #999;
}
</style>