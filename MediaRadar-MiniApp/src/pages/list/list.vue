<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">←</view>
      <view class="title">舆情列表</view>
      <view class="action-btn">🔍</view>
    </view>

    <scroll-view scroll-y class="content">
      <view class="filter-bar">
        <view class="filter-btn" @click="openModal('keyword')">
          {{ currentKeyword === 'all' ? '全部关键词' : currentKeyword }} ▾
        </view>
        <view class="filter-btn" @click="openModal('platform')">
          {{ currentPlatform === 'all' ? '全部平台' : (currentPlatform === 'wb' ? '微博' : '小红书') }} ▾
        </view>
        <view class="filter-btn" @click="openModal('sentiment')">
          {{ currentSentiment === 'all' ? '全部情感' : (currentSentiment === 'negative' ? '负面' : (currentSentiment === 'positive' ? '正面' : '中性')) }} ▾
        </view>
      </view>

      <view class="list-summary">
        共加载 {{ filteredList.length }} 条 · 负面 
        <text class="negative-count">{{ negativeCount }}</text> 条
      </view>

      <view 
        class="list-item" 
        :class="item.riskClass"
        v-for="(item, index) in filteredList" 
        :key="index"
        @click="goToDetail(item)"
      >
        <view class="list-item-header">
          <view class="platform-tag" :class="item.platform === 'wb' ? 'weibo' : 'xiaohongshu'">
            {{ item.platform === 'wb' ? '📘 微博' : '📕 小红书' }}
          </view>
          <view class="sentiment-tag" :class="item.riskClass">{{ item.riskText }}</view>
        </view>
        <view class="list-item-content">
          <text v-if="item.core_issue && item.core_issue !== '无异常'" style="font-weight: bold;">【{{item.core_issue}}】 </text>
          {{ item.report }}
        </view>
        <view class="list-item-footer">
          <view class="list-item-meta">🏷️ {{ item.keyword || '监控词' }} · {{ item.create_time }}</view>
          <view class="list-item-actions">
            <text class="action-link">查看详情</text>
          </view>
        </view>
      </view>

      <view v-if="filteredList.length === 0" class="load-more">没有符合条件的数据</view>
      <view v-else class="load-more">到底了...</view>
    </scroll-view>

    <view class="modal-overlay" :class="{ active: activeModal === 'keyword' }" @click="closeModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header"><view class="title">选择关键词</view></view>
        <view class="modal-options">
          <view class="modal-option" :class="{ selected: currentKeyword === 'all' }" @click="selectFilter('keyword', 'all')">
            <view class="checkbox">{{ currentKeyword === 'all' ? '✓' : '' }}</view>
            <view class="label">全部关键词</view>
          </view>
          <view 
            class="modal-option" 
            v-for="kw in uniqueKeywords" 
            :key="kw"
            :class="{ selected: currentKeyword === kw }" 
            @click="selectFilter('keyword', kw)"
          >
            <view class="checkbox">{{ currentKeyword === kw ? '✓' : '' }}</view>
            <view class="label">{{ kw }}</view>
          </view>
        </view>
        <button class="modal-btn" @click="closeModal">确定</button>
      </view>
    </view>

    <view class="modal-overlay" :class="{ active: activeModal === 'platform' }" @click="closeModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header"><view class="title">选择平台</view></view>
        <view class="modal-options">
          <view class="modal-option" :class="{ selected: currentPlatform === 'all' }" @click="selectFilter('platform', 'all')">
            <view class="checkbox">{{ currentPlatform === 'all' ? '✓' : '' }}</view>
            <view class="label">全部平台</view>
          </view>
          <view class="modal-option" :class="{ selected: currentPlatform === 'wb' }" @click="selectFilter('platform', 'wb')">
            <view class="checkbox">{{ currentPlatform === 'wb' ? '✓' : '' }}</view>
            <view class="label">📘 微博</view>
          </view>
          <view class="modal-option" :class="{ selected: currentPlatform === 'xhs' }" @click="selectFilter('platform', 'xhs')">
            <view class="checkbox">{{ currentPlatform === 'xhs' ? '✓' : '' }}</view>
            <view class="label">📕 小红书</view>
          </view>
        </view>
        <button class="modal-btn" @click="closeModal">确定</button>
      </view>
    </view>

    <view class="modal-overlay" :class="{ active: activeModal === 'sentiment' }" @click="closeModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header"><view class="title">选择情感</view></view>
        <view class="modal-options">
          <view class="modal-option" :class="{ selected: currentSentiment === 'all' }" @click="selectFilter('sentiment', 'all')">
            <view class="checkbox">{{ currentSentiment === 'all' ? '✓' : '' }}</view>
            <view class="label">全部情感</view>
          </view>
          <view class="modal-option" :class="{ selected: currentSentiment === 'positive' }" @click="selectFilter('sentiment', 'positive')">
            <view class="checkbox">{{ currentSentiment === 'positive' ? '✓' : '' }}</view>
            <view class="label">😊 正面 (低风险)</view>
          </view>
          <view class="modal-option" :class="{ selected: currentSentiment === 'neutral' }" @click="selectFilter('sentiment', 'neutral')">
            <view class="checkbox">{{ currentSentiment === 'neutral' ? '✓' : '' }}</view>
            <view class="label">😐 中性 (中风险)</view>
          </view>
          <view class="modal-option" :class="{ selected: currentSentiment === 'negative' }" @click="selectFilter('sentiment', 'negative')">
            <view class="checkbox">{{ currentSentiment === 'negative' ? '✓' : '' }}</view>
            <view class="label">😡 负面 (高风险)</view>
          </view>
        </view>
        <button class="modal-btn" @click="closeModal">确定</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const dataList = ref([])
const activeModal = ref(null)

const currentKeyword = ref('all')
const currentPlatform = ref('all')
const currentSentiment = ref('all')

const goBack = () => uni.navigateBack()
const openModal = (type) => activeModal.value = type
const closeModal = () => activeModal.value = null

const selectFilter = (type, value) => {
  if (type === 'keyword') currentKeyword.value = value
  if (type === 'platform') currentPlatform.value = value
  if (type === 'sentiment') currentSentiment.value = value
  // 可选：选中后立刻关弹窗，如果想等用户点确定，可以把下一行注释掉
  // closeModal() 
}

// 自动提取库里存在的唯一关键词
const uniqueKeywords = computed(() => {
  const keys = new Set(dataList.value.map(item => item.keyword))
  return Array.from(keys).filter(k => k)
})

// ✨ 核心：通过前端响应式完美实现多重过滤
const filteredList = computed(() => {
  return dataList.value.filter(item => {
    const matchKeyword = currentKeyword.value === 'all' || item.keyword === currentKeyword.value
    const matchPlatform = currentPlatform.value === 'all' || item.platform === currentPlatform.value
    const matchSentiment = currentSentiment.value === 'all' || item.riskClass === currentSentiment.value
    return matchKeyword && matchPlatform && matchSentiment
  })
})

const negativeCount = computed(() => {
  return filteredList.value.filter(item => item.riskClass === 'negative').length
})

// 跳转到详情页，并把这行数据传过去
const goToDetail = (item) => {
  uni.navigateTo({
    url: `/pages/list/detail?data=${encodeURIComponent(JSON.stringify(item))}`
  })
}

const fetchYqData = () => {
  uni.showLoading({ title: '加载中...' }) 
  uni.request({
    url: 'http://127.0.0.1:8000/api/yq_list',
    method: 'GET',
    success: (res) => {
      uni.hideLoading() 
      if (res.data && res.data.code === 200) {
        const rawData = res.data.data
        dataList.value = rawData.map(item => {
          return {
            id: item.id,
            keyword: item.keyword || '北京银行',
            platform: item.platform === '微博' ? 'wb' : 'xhs', 
            riskClass: item.sentiment, 
            riskText: item.risk === '高风险' ? '负面' : (item.risk === '低风险' ? '正面' : '中性'),
            core_issue: item.core_issue,  
            report: item.report,
            url: item.url,          
            create_time: item.create_time ? item.create_time.substring(5, 16) : '刚刚' 
          }
        })
      }
    },
    fail: () => {
      uni.hideLoading()
      uni.showToast({ title: '网络请求失败', icon: 'none' })
    }
  })
}

onMounted(() => {
  fetchYqData()
})
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #f5f5f5; }
.header { height: 100rpx; background-color: #ffffff; display: flex; justify-content: space-between; align-items: center; padding: 0 32rpx; border-bottom: 2rpx solid #eee; z-index: 10; }
.header .back-btn, .header .action-btn { font-size: 40rpx; color: #333; cursor: pointer; width: 60rpx; }
.header .title { font-size: 36rpx; font-weight: 600; color: #333; }

.content { flex: 1; overflow-y: auto; padding: 32rpx; box-sizing: border-box; }

.filter-bar { display: flex; gap: 16rpx; margin-bottom: 24rpx; }
.filter-btn { flex: 1; padding: 20rpx 16rpx; background-color: #fff; border: 2rpx solid #e8e8e8; border-radius: 16rpx; font-size: 26rpx; color: #666; display: flex; align-items: center; justify-content: center; gap: 8rpx; }

.list-summary { padding: 24rpx 32rpx; background-color: #fff; border-radius: 16rpx; margin-bottom: 24rpx; font-size: 28rpx; color: #666; }
.list-summary .negative-count { color: #ff4d4f; font-weight: 600; }

.list-item { background-color: #fff; border-radius: 24rpx; padding: 32rpx; margin-bottom: 24rpx; box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.05); cursor: pointer; }
.list-item.negative { border-left: 8rpx solid #ff4d4f; }
.list-item.positive { border-left: 8rpx solid #52c41a; }
.list-item.neutral { border-left: 8rpx solid #faad14; }

.list-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20rpx; }
.platform-tag { display: flex; align-items: center; gap: 12rpx; font-size: 26rpx; font-weight: 500; }
.platform-tag.xiaohongshu { color: #ff2442; }
.platform-tag.weibo { color: #ff8200; }

.sentiment-tag { padding: 8rpx 20rpx; border-radius: 24rpx; font-size: 24rpx; font-weight: 500; }
.sentiment-tag.negative { background-color: #fff2f0; color: #ff4d4f; }
.sentiment-tag.positive { background-color: #f6ffed; color: #52c41a; }
.sentiment-tag.neutral { background-color: #fffbe6; color: #faad14; }

.list-item-content { font-size: 28rpx; color: #333; line-height: 1.6; margin-bottom: 24rpx; }
.list-item-footer { display: flex; justify-content: space-between; align-items: center; padding-top: 24rpx; border-top: 2rpx solid #f0f0f0; }
.list-item-meta { font-size: 24rpx; color: #999; }
.action-link { font-size: 26rpx; color: #667eea; }

.load-more { text-align: center; padding: 32rpx; color: #999; font-size: 28rpx; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.5); z-index: 100; display: flex; align-items: flex-end; justify-content: center; visibility: hidden; opacity: 0; transition: all 0.3s; }
.modal-overlay.active { visibility: visible; opacity: 1; }
.modal-content { width: 100%; background-color: #fff; border-radius: 40rpx 40rpx 0 0; padding: 48rpx; box-sizing: border-box; transform: translateY(100%); transition: transform 0.3s ease; }
.modal-overlay.active .modal-content { transform: translateY(0); }

.modal-header { text-align: center; margin-bottom: 48rpx; }
.modal-header .title { font-size: 36rpx; font-weight: 600; color: #333; }
.modal-options { margin-bottom: 40rpx; max-height: 400rpx; overflow-y: auto; }
.modal-option { display: flex; align-items: center; padding: 28rpx; border: 4rpx solid #e8e8e8; border-radius: 20rpx; margin-bottom: 20rpx; transition: all 0.2s; }
.modal-option.selected { border-color: #667eea; background-color: #f0f0ff; }
.modal-option .checkbox { width: 44rpx; height: 44rpx; border: 4rpx solid #ddd; border-radius: 12rpx; margin-right: 24rpx; display: flex; align-items: center; justify-content: center; font-size: 28rpx; color: #fff; }
.modal-option.selected .checkbox { background-color: #667eea; border-color: #667eea; }
.modal-option .label { font-size: 30rpx; color: #333; }
.modal-btn { width: 100%; padding: 24rpx; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; border-radius: 24rpx; font-size: 32rpx; font-weight: 500; color: #fff; margin-top: 10rpx; }
</style>