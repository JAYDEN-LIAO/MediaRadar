<template>
  <view class="page-container">
    <view class="header">
      <view class="status-dot"></view>
      <view class="title">话题列表</view>
    </view>

    <scroll-view scroll-y class="content">
      <view class="filter-bar">
        <view class="filter-btn" @click="openModal('keyword')">
          <text class="filter-text">{{ currentKeyword === 'all' ? '全部关键词' : currentKeyword }}</text>
          <text class="filter-arrow">▾</text>
        </view>
        <view class="filter-btn" @click="openModal('platform')">
          <text class="filter-text">{{ currentPlatformName }}</text>
          <text class="filter-arrow">▾</text>
        </view>
        <view class="filter-btn" @click="openModal('sentiment')">
          <text class="filter-text">{{ currentSentiment === 'all' ? '全部情感' : (currentSentiment === 'negative' ? '负面' : (currentSentiment === 'positive' ? '正面' : '中性')) }}</text>
          <text class="filter-arrow">▾</text>
        </view>
        <view class="filter-btn" @click="openModal('status')">
          <text class="filter-text">{{ currentStatus === 'all' ? '全部状态' : (currentStatus === 1 ? '已处理' : '未处理') }}</text>
          <text class="filter-arrow">▾</text>
        </view>
      </view>

      <view class="list-summary">
        <text class="summary-text">共 <text class="count">{{ filteredList.length }}</text> 个话题</text>
        <text class="separator">·</text>
        <text class="summary-text">负面 <text class="count danger">{{ negativeCount }}</text> 个</text>
      </view>

      <!-- 话题卡片 -->
      <view
        class="topic-card"
        v-for="(item, index) in filteredList"
        :key="index"
        @click="goToTopic(item)"
      >
        <view class="topic-card-header">
          <view class="topic-title-row">
            <text class="topic-name">{{ item.topic_name || '未知话题' }}</text>
            <view class="sentiment-tag" :class="item.risk_class">
              <view class="sentiment-dot"></view>
              {{ item.sentiment }}
            </view>
          </view>
          <view class="signal-tag" :class="getSignalClass(item.evolution_signal)" v-if="item.evolution_signal !== 'unknown'">
            {{ getSignalText(item.evolution_signal) }}
          </view>
        </view>

        <view class="topic-summary">
          {{ item.cluster_summary || '暂无摘要' }}
        </view>

        <view class="topic-meta">
          <view class="platform-dots">
            <view
              class="plat-dot"
              v-for="(plat, idx) in (item.platforms || []).slice(0, 5)"
              :key="idx"
              :class="getPlatClass(plat)"
              :title="plat"
            ></view>
            <text class="plat-names">{{ (item.platforms || []).join('、') }}</text>
          </view>
          <view class="topic-stats">
            <text class="stat-item">{{ item.post_count }} 条帖子</text>
            <text class="dot-sep">·</text>
            <text class="stat-item">{{ item.first_seen ? item.first_seen.substring(5, 16) : '' }}</text>
          </view>
        </view>

        <view class="topic-footer">
          <view class="list-item-meta">
            <text class="tag">{{ item.keyword || '监控词' }}</text>
            <text class="dot-sep">·</text>
            <text class="core-issue" v-if="item.core_issue && item.core_issue !== '无异常'">【{{item.core_issue}}】</text>
          </view>
          <view class="status-action" :class="{ processed: item.is_processed === 1 }">
            {{ item.is_processed === 1 ? '已处理' : '待处理' }}
            <text class="action-arrow">→</text>
          </view>
        </view>
      </view>

      <view v-if="filteredList.length === 0" class="empty-state">
        <text class="empty-text">暂无符合条件的话题</text>
      </view>
      <view v-else class="load-more">已加载全部</view>
    </scroll-view>

    <!-- 筛选弹窗（复用，关键词/平台/情感/状态） -->
    <view class="modal-overlay" :class="{ active: activeModal === 'keyword' }" @click="closeModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">选择关键词</text>
          <view class="modal-close" @click="closeModal">×</view>
        </view>
        <view class="modal-options">
          <view class="modal-option" :class="{ selected: currentKeyword === 'all' }" @click="selectFilter('keyword', 'all')">
            <view class="radio"><view class="radio-dot" v-if="currentKeyword === 'all'"></view></view>
            <text class="option-label">全部关键词</text>
          </view>
          <view class="modal-option" :class="{ selected: currentKeyword === kw }" v-for="kw in uniqueKeywords" :key="kw" @click="selectFilter('keyword', kw)">
            <view class="radio"><view class="radio-dot" v-if="currentKeyword === kw"></view></view>
            <text class="option-label">{{ kw }}</text>
          </view>
        </view>
        <button class="modal-btn" @click="closeModal">确定</button>
      </view>
    </view>

    <view class="modal-overlay" :class="{ active: activeModal === 'platform' }" @click="closeModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">选择平台</text>
          <view class="modal-close" @click="closeModal">×</view>
        </view>
        <view class="modal-options">
          <view class="modal-option" :class="{ selected: currentPlatform === 'all' }" @click="selectFilter('platform', 'all')">
            <view class="radio"><view class="radio-dot" v-if="currentPlatform === 'all'"></view></view>
            <text class="option-label">全部平台</text>
          </view>
          <view class="modal-option" :class="{ selected: currentPlatform === plat.val }" v-for="plat in platformOptions" :key="plat.val" @click="selectFilter('platform', plat.val)">
            <view class="radio"><view class="radio-dot" v-if="currentPlatform === plat.val"></view></view>
            <view class="platform-option">
              <view class="platform-dot" :class="plat.val"></view>
              <text class="option-label">{{ plat.label }}</text>
            </view>
          </view>
        </view>
        <button class="modal-btn" @click="closeModal">确定</button>
      </view>
    </view>

    <view class="modal-overlay" :class="{ active: activeModal === 'sentiment' }" @click="closeModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">选择情感</text>
          <view class="modal-close" @click="closeModal">×</view>
        </view>
        <view class="modal-options">
          <view class="modal-option" :class="{ selected: currentSentiment === 'all' }" @click="selectFilter('sentiment', 'all')">
            <view class="radio"><view class="radio-dot" v-if="currentSentiment === 'all'"></view></view>
            <text class="option-label">全部情感</text>
          </view>
          <view class="modal-option" :class="{ selected: currentSentiment === 'negative' }" @click="selectFilter('sentiment', 'negative')">
            <view class="radio"><view class="radio-dot" v-if="currentSentiment === 'negative'"></view></view>
            <view class="sentiment-option negative"><view class="sentiment-dot"></view><text class="option-label">负面 (高风险)</text></view>
          </view>
          <view class="modal-option" :class="{ selected: currentSentiment === 'neutral' }" @click="selectFilter('sentiment', 'neutral')">
            <view class="radio"><view class="radio-dot" v-if="currentSentiment === 'neutral'"></view></view>
            <view class="sentiment-option neutral"><view class="sentiment-dot"></view><text class="option-label">中性 (中风险)</text></view>
          </view>
          <view class="modal-option" :class="{ selected: currentSentiment === 'positive' }" @click="selectFilter('sentiment', 'positive')">
            <view class="radio"><view class="radio-dot" v-if="currentSentiment === 'positive'"></view></view>
            <view class="sentiment-option positive"><view class="sentiment-dot"></view><text class="option-label">正面 (低风险)</text></view>
          </view>
        </view>
        <button class="modal-btn" @click="closeModal">确定</button>
      </view>
    </view>

    <view class="modal-overlay" :class="{ active: activeModal === 'status' }" @click="closeModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">选择状态</text>
          <view class="modal-close" @click="closeModal">×</view>
        </view>
        <view class="modal-options">
          <view class="modal-option" :class="{ selected: currentStatus === 'all' }" @click="selectFilter('status', 'all')">
            <view class="radio"><view class="radio-dot" v-if="currentStatus === 'all'"></view></view>
            <text class="option-label">全部状态</text>
          </view>
          <view class="modal-option" :class="{ selected: currentStatus === 0 }" @click="selectFilter('status', 0)">
            <view class="radio"><view class="radio-dot" v-if="currentStatus === 0"></view></view>
            <text class="option-label">未处理</text>
          </view>
          <view class="modal-option" :class="{ selected: currentStatus === 1 }" @click="selectFilter('status', 1)">
            <view class="radio"><view class="radio-dot" v-if="currentStatus === 1"></view></view>
            <text class="option-label">已处理</text>
          </view>
        </view>
        <button class="modal-btn" @click="closeModal">确定</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getTopicList } from '../../utils/api.js'

const dataList = ref([])
const activeModal = ref(null)

const currentKeyword = ref('all')
const currentPlatform = ref('all')
const currentSentiment = ref('all')
const currentStatus = ref('all')

const openModal = (type) => activeModal.value = type
const closeModal = () => activeModal.value = null

const platformOptions = [
  { val: 'all', label: '全部平台' },
  { val: 'wb', label: '微博' },
  { val: 'xhs', label: '小红书' },
  { val: 'bili', label: 'B站' },
  { val: 'zhihu', label: '知乎' },
  { val: 'dy', label: '抖音' },
  { val: 'ks', label: '快手' },
  { val: 'tieba', label: '贴吧' }
]

const platValToName = {
  '微博': 'wb', '小红书': 'xhs', 'B站': 'bili', '知乎': 'zhihu', '抖音': 'dy', '快手': 'ks', '贴吧': 'tieba'
}

const currentPlatformName = computed(() => {
  const plat = platformOptions.find(p => p.val === currentPlatform.value)
  return plat ? plat.label : '全部平台'
})

const selectFilter = (type, value) => {
  if (type === 'keyword') currentKeyword.value = value
  if (type === 'platform') currentPlatform.value = value
  if (type === 'sentiment') currentSentiment.value = value
  if (type === 'status') currentStatus.value = value
}

const uniqueKeywords = computed(() => {
  const keys = new Set()
  dataList.value.forEach(item => {
    if (item.keyword) keys.add(item.keyword)
  })
  return Array.from(keys)
})

const filteredList = computed(() => {
  return dataList.value.filter(item => {
    const matchKw = currentKeyword.value === 'all' || item.keyword === currentKeyword.value
    // 平台筛选：话题的 platforms 是中文名称列表
    let matchPlat = true
    if (currentPlatform.value !== 'all') {
      const targetName = platformOptions.find(p => p.val === currentPlatform.value)?.label || ''
      matchPlat = (item.platforms || []).includes(targetName)
    }
    const matchSent = currentSentiment.value === 'all' || item.risk_class === currentSentiment.value
    const matchStatus = currentStatus.value === 'all' || (item.is_processed || 0) === currentStatus.value
    return matchKw && matchPlat && matchSent && matchStatus
  })
})

const negativeCount = computed(() => {
  return filteredList.value.filter(item => item.risk_class === 'negative').length
})

const goToTopic = (item) => {
  uni.navigateTo({
    url: `/pages/list/topic?topic_id=${item.topic_id}&topic_name=${encodeURIComponent(item.topic_name || '')}`
  })
}

const fetchTopicList = () => {
  uni.showLoading({ title: '加载中...' })
  getTopicList({ limit: 100 })
    .then((res) => {
      uni.hideLoading()
      if (res && res.code === 200) {
        dataList.value = (res.data || []).map(item => ({
          topic_id: item.topic_id,
          keyword: item.keyword,
          topic_name: item.topic_name,
          cluster_summary: item.cluster_summary,
          risk_level: item.risk_level,
          risk_class: item.risk_class,  // negative/positive/neutral
          sentiment: item.sentiment,     // 负面/正面/中性
          platforms: item.platforms || [],
          post_count: item.post_count || 0,
          first_seen: item.first_seen || '',
          last_seen: item.last_seen || '',
          core_issue: item.core_issue,
          is_processed: item.is_processed || 0,
          evolution_signal: item.evolution_signal || 'unknown',
        }))
      }
    })
    .catch(() => {
      uni.hideLoading()
      uni.showToast({ title: '网络请求失败', icon: 'none' })
    })
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

// 平台小圆点颜色
const getPlatClass = (platName) => {
  const map = { '微博': 'wb', '小红书': 'xhs', 'B站': 'bili', '知乎': 'zhihu', '抖音': 'dy', '快手': 'ks', '贴吧': 'tieba' }
  return map[platName] || ''
}

onMounted(() => {
  fetchTopicList()
})
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #F8FAFC; }

.header {
  height: 100rpx;
  background-color: #FFFFFF;
  display: flex;
  align-items: center;
  padding: 0 32rpx;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  z-index: 10;
}

.status-dot { width: 8rpx; height: 8rpx; border-radius: 50%; background-color: #0891B2; margin-right: 16rpx; }

.header .title {
  font-size: 34rpx;
  font-weight: 600;
  color: #0F172A;
  letter-spacing: 1rpx;
  flex: 1;
}

.content { flex: 1; overflow-y: auto; padding: 24rpx; box-sizing: border-box; }

.filter-bar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }

.filter-btn {
  flex: 1;
  padding: 18rpx 6rpx;
  background-color: #FFFFFF;
  border: 1rpx solid #E2E8F0;
  border-radius: 10rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4rpx;
  white-space: nowrap;
  overflow: hidden;
}

.filter-text { font-size: 24rpx; color: #475569; overflow: hidden; text-overflow: ellipsis; }

.filter-arrow { font-size: 20rpx; color: #94A3B8; flex-shrink: 0; }

.list-summary {
  display: flex;
  align-items: center;
  padding: 20rpx 24rpx;
  background-color: #FFFFFF;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
}

.summary-text { font-size: 26rpx; color: #64748B; }
.separator { margin: 0 12rpx; color: #CBD5E1; }
.count { font-weight: 600; color: #0F172A; font-family: 'JetBrains Mono', monospace; }
.count.danger { color: #DC2626; }

/* 话题卡片 */
.topic-card {
  background-color: #FFFFFF;
  border-radius: 14rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 1rpx 3rpx rgba(0,0,0,0.04);
  position: relative;
  border-left: 6rpx solid #667eea;
}

.topic-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
}

.topic-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex: 1;
  overflow: hidden;
}

.topic-name {
  font-size: 30rpx;
  font-weight: 700;
  color: #0F172A;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.signal-tag {
  font-size: 22rpx;
  font-weight: 600;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  flex-shrink: 0;
}

.signal-red { background-color: #fff2f0; color: #ff4d4f; }
.signal-yellow { background-color: #fffbe6; color: #faad14; }
.signal-green { background-color: #f6ffed; color: #52c41a; }
.signal-gray { background-color: #f5f5f5; color: #999; }

.topic-summary {
  font-size: 26rpx;
  color: #64748B;
  line-height: 1.6;
  margin-bottom: 16rpx;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.topic-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
}

.platform-dots {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.plat-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
}

.plat-dot.wb { background-color: #FF8200; }
.plat-dot.xhs { background-color: #FF2442; }
.plat-dot.bili { background-color: #FB7299; }
.plat-dot.zhihu { background-color: #0066FF; }
.plat-dot.dy { background-color: #1C1C1E; }
.plat-dot.ks { background-color: #FF5000; }
.plat-dot.tieba { background-color: #3388FF; }

.plat-names { font-size: 22rpx; color: #94A3B8; margin-left: 6rpx; }

.topic-stats { display: flex; align-items: center; }
.stat-item { font-size: 22rpx; color: #94A3B8; font-family: 'JetBrains Mono', monospace; }
.dot-sep { margin: 0 8rpx; color: #CBD5E1; }

.topic-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 14rpx;
  border-top: 1rpx solid #F1F5F9;
}

.list-item-meta { display: flex; align-items: center; font-size: 24rpx; color: #94A3B8; }
.tag { background-color: #F1F5F9; padding: 4rpx 10rpx; border-radius: 4rpx; font-size: 22rpx; }
.dot-sep { margin: 0 10rpx; }
.core-issue { font-weight: 600; color: #667eea; font-size: 24rpx; }

.status-action { font-size: 26rpx; font-weight: 500; color: #0891B2; }
.status-action.processed { color: #94A3B8; }
.action-arrow { margin-left: 4rpx; }

/* 情感标签 */
.sentiment-tag {
  display: flex;
  align-items: center;
  padding: 6rpx 14rpx;
  border-radius: 6rpx;
  font-size: 22rpx;
  font-weight: 500;
  flex-shrink: 0;
}

.sentiment-dot { width: 6rpx; height: 6rpx; border-radius: 50%; margin-right: 8rpx; }
.sentiment-tag.negative { background-color: #FEF2F2; color: #DC2626; }
.sentiment-tag.negative .sentiment-dot { background-color: #DC2626; }
.sentiment-tag.positive { background-color: #F0FDF4; color: #059669; }
.sentiment-tag.positive .sentiment-dot { background-color: #059669; }
.sentiment-tag.neutral { background-color: #FFFBEB; color: #D97706; }
.sentiment-tag.neutral .sentiment-dot { background-color: #D97706; }

.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80rpx 0; }
.empty-text { font-size: 28rpx; color: #94A3B8; }

.load-more { text-align: center; padding: 32rpx; color: #94A3B8; font-size: 26rpx; }

/* Modal（复用，样式与原 list.vue 一致） */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(15, 23, 42, 0.5); z-index: 100;
  display: flex; align-items: flex-end; justify-content: center;
  visibility: hidden; opacity: 0; transition: all 0.2s ease;
}
.modal-overlay.active { visibility: visible; opacity: 1; }

.modal-content {
  width: 100%; background-color: #FFFFFF;
  border-radius: 20rpx 20rpx 0 0;
  padding: 32rpx;
  padding-bottom: calc(32rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  transform: translateY(100%); transition: transform 0.25s ease;
}
.modal-overlay.active .modal-content { transform: translateY(0); }

.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28rpx; }
.modal-title { font-size: 34rpx; font-weight: 600; color: #0F172A; }
.modal-close { width: 56rpx; height: 56rpx; display: flex; align-items: center; justify-content: center; font-size: 40rpx; color: #94A3B8; }
.modal-options { margin-bottom: 28rpx; max-height: 480rpx; overflow-y: auto; }

.modal-option {
  display: flex; align-items: center; padding: 22rpx;
  border: 1rpx solid #E2E8F0; border-radius: 12rpx; margin-bottom: 14rpx; transition: all 0.15s ease;
}
.modal-option.selected { border-color: #0F172A; background-color: #F8FAFC; }

.radio {
  width: 36rpx; height: 36rpx; border: 2rpx solid #CBD5E1; border-radius: 50%;
  margin-right: 18rpx; display: flex; align-items: center; justify-content: center;
}
.modal-option.selected .radio { border-color: #0F172A; }
.radio-dot { width: 18rpx; height: 18rpx; border-radius: 50%; background-color: #0F172A; }

.option-label { font-size: 30rpx; color: #334155; }
.platform-option { display: flex; align-items: center; }
.platform-dot { width: 8rpx; height: 8rpx; border-radius: 50%; margin-right: 10rpx; }
.platform-dot.wb { background-color: #FF8200; }
.platform-dot.xhs { background-color: #FF2442; }
.platform-dot.bili { background-color: #FB7299; }
.platform-dot.zhihu { background-color: #0066FF; }
.platform-dot.dy { background-color: #1C1C1E; }
.platform-dot.ks { background-color: #FF5000; }
.platform-dot.tieba { background-color: #3388FF; }

.sentiment-option { display: flex; align-items: center; }
.sentiment-option .sentiment-dot { width: 8rpx; height: 8rpx; border-radius: 50%; margin-right: 10rpx; }
.sentiment-option.positive .sentiment-dot { background-color: #059669; }
.sentiment-option.neutral .sentiment-dot { background-color: #D97706; }
.sentiment-option.negative .sentiment-dot { background-color: #DC2626; }

.modal-btn {
  width: 100%; padding: 26rpx; background-color: #0F172A; border: none;
  border-radius: 12rpx; font-size: 32rpx; font-weight: 500; color: #FFFFFF;
}
.modal-btn:active { background-color: #1E293B; }
</style>
