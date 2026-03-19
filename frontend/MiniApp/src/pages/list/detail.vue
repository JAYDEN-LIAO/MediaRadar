<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">←</view>
      <view class="title">舆情详情</view>
      <view class="action-btn">↗️</view>
    </view>
    
    <scroll-view scroll-y class="content">
      <view class="detail-source">
        <view class="platform-icon">{{ itemData.platform === 'wb' ? '📘' : '📕' }}</view>
        <view class="platform-info">
          <view class="name">{{ itemData.platform === 'wb' ? '微博' : '小红书' }}</view>
        </view>
        <view class="sentiment-tag" :class="itemData.riskClass">{{ itemData.riskText }}</view>
      </view>
      
      <view class="detail-content">
        <view class="text">
          {{ itemData.report || '暂无详细内容' }}
        </view>
        <view class="tags" v-if="itemData.core_issue && itemData.core_issue !== '无异常'">
          <view class="tag">#{{ itemData.core_issue }}</view>
        </view>
      </view>
      
      <view class="detail-info">
        <view class="info-row">
          <view class="info-label">关联关键词</view>
          <view class="info-value">{{ itemData.keyword }}</view>
        </view>
        <view class="info-row">
          <view class="info-label">发布时间</view>
          <view class="info-value">{{ itemData.create_time }}</view>
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
            {{ itemData.riskClass === 'negative' ? '高风险预警' : '常规提示' }}
          </view>
        </view>
      </view>
      
      <view class="detail-actions">
        <view class="detail-btn secondary" @click="openOriginalUrl">查看原文</view>
        <view class="detail-btn primary" @click="markAsProcessed">标记已处理</view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const itemData = ref({})

// 页面加载时，接收列表页传过来的数据
onLoad((options) => {
  if (options.data) {
    try {
      itemData.value = JSON.parse(decodeURIComponent(options.data))
    } catch (e) {
      console.error('解析详情数据失败', e)
    }
  }
})

const goBack = () => uni.navigateBack()

// 点击跳转外链逻辑（如果爬虫抓到了 url）
const openOriginalUrl = () => {
  if (itemData.value.url) {
    // 微信小程序里不能直接跳外链，通常复制到剪贴板
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

const markAsProcessed = () => {
  uni.showToast({ title: '已标记处理', icon: 'success' })
  setTimeout(() => goBack(), 1000)
}
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #f5f5f5; }
.header { height: 100rpx; background-color: #ffffff; display: flex; justify-content: space-between; align-items: center; padding: 0 32rpx; border-bottom: 2rpx solid #eee; z-index: 10; }
.header .back-btn, .header .action-btn { font-size: 40rpx; color: #333; cursor: pointer; width: 60rpx; }
.header .title { font-size: 36rpx; font-weight: 600; color: #333; }

.content { flex: 1; overflow-y: auto; padding: 32rpx; box-sizing: border-box; }

.detail-source { display: flex; align-items: center; gap: 24rpx; padding: 32rpx; background-color: #fff; border-radius: 24rpx; margin-bottom: 24rpx; }
.detail-source .platform-icon { font-size: 72rpx; }
.detail-source .platform-info .name { font-size: 32rpx; font-weight: 600; color: #333; }
.detail-source .sentiment-tag { margin-left: auto; padding: 8rpx 24rpx; border-radius: 24rpx; font-size: 24rpx; font-weight: 500; }
.sentiment-tag.negative { background-color: #fff2f0; color: #ff4d4f; }
.sentiment-tag.positive { background-color: #f6ffed; color: #52c41a; }
.sentiment-tag.neutral { background-color: #fffbe6; color: #faad14; }

.detail-content { background-color: #fff; border-radius: 24rpx; padding: 32rpx; margin-bottom: 24rpx; }
.detail-content .text { font-size: 30rpx; line-height: 1.8; color: #333; }
.detail-content .tags { margin-top: 32rpx; padding-top: 24rpx; border-top: 2rpx solid #f0f0f0; }
.detail-content .tag { display: inline-block; padding: 8rpx 20rpx; background-color: #f0f0f0; border-radius: 24rpx; font-size: 24rpx; color: #666; margin-right: 16rpx; }

.detail-info { background-color: #fff; border-radius: 24rpx; padding: 32rpx; margin-bottom: 24rpx; }
.detail-info .info-row { display: flex; justify-content: space-between; padding: 24rpx 0; border-bottom: 2rpx solid #f0f0f0; }
.detail-info .info-row:last-child { border-bottom: none; }
.detail-info .info-label { font-size: 28rpx; color: #999; }
.detail-info .info-value { font-size: 28rpx; color: #333; }
.detail-info .info-value.negative { color: #ff4d4f; }
.detail-info .info-value.unprocessed { color: #faad14; }

.detail-actions { display: flex; gap: 24rpx; margin-top: 16rpx; padding-bottom: 40rpx;}
.detail-btn { flex: 1; padding: 28rpx; border-radius: 24rpx; font-size: 30rpx; font-weight: 500; text-align: center; }
.detail-btn.primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; }
.detail-btn.secondary { background-color: #fff; color: #667eea; border: 4rpx solid #667eea; }
</style>