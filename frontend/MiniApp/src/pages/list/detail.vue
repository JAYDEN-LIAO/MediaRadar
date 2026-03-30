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

</style>