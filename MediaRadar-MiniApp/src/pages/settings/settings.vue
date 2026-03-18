<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">‹</view>
      <view class="title">监控设置</view>
      <view class="action-btn"></view>
    </view>

    <scroll-view scroll-y class="content">
      <view class="settings-section">
        <view class="section-header">
          <text class="icon">🎯</text>
          <text class="title">监控关键词</text>
          <text class="count">已添加 1/5</text>
        </view>
        <view class="keyword-item">
          <view class="keyword-name">北京银行</view>
          <view class="keyword-platforms">
            <text class="platform-check">☑️ 微博</text>
            <text class="platform-check">☑️ 小红书</text>
          </view>
          <view class="edit-btn">编辑规则</view>
        </view>
        <view class="add-keyword-btn">
          <view>+ 添加新关键词</view>
          <view class="sub-text">支持品牌名、高管名、产品名等</view>
        </view>
      </view>

      <view class="settings-section">
        <view class="section-header">
          <text class="icon">🌐</text>
          <text class="title">平台抓取设置</text>
        </view>
        <view class="setting-row">
          <view class="label">微博 (Weibo)</view>
          <switch checked color="#52c41a" style="transform:scale(0.8)" />
        </view>
        <view class="setting-row">
          <view class="label">小红书 (Xiaohongshu)</view>
          <switch checked color="#52c41a" style="transform:scale(0.8)" />
        </view>
        <view class="setting-row">
          <view class="label">抖音 (Douyin)</view>
          <switch color="#52c41a" style="transform:scale(0.8)" />
        </view>
      </view>

      <view class="settings-section">
        <view class="section-header">
          <text class="icon">🔔</text>
          <text class="title">通知与报警</text>
        </view>
        <view class="setting-row">
          <view class="label">高风险立刻报警</view>
          <switch checked color="#52c41a" style="transform:scale(0.8)" />
        </view>
        <view class="info-box">
          <view class="tip">开启高风险报警后，当大模型研判出现严重负面时，将立刻通过钉钉/微信推送给您。</view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
const goBack = () => uni.navigateBack()
</script>

<style scoped>
.content { padding: 32rpx; }
.settings-section { background-color: #fff; border-radius: 24rpx; padding: 32rpx; margin-bottom: 24rpx; box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.05);}
.section-header { display: flex; align-items: center; margin-bottom: 32rpx; }
.section-header .icon { font-size: 40rpx; margin-right: 16rpx; }
.section-header .title { font-size: 32rpx; font-weight: 600; color: #333; }
.section-header .count { margin-left: auto; font-size: 28rpx; color: #667eea; }

.keyword-item { padding: 28rpx; background-color: #f9f9f9; border-radius: 20rpx; margin-bottom: 20rpx; position: relative;}
.keyword-name { font-size: 30rpx; font-weight: 600; color: #333; margin-bottom: 16rpx; }
.keyword-platforms { display: flex; gap: 24rpx; }
.platform-check { font-size: 26rpx; color: #666; }
.edit-btn { position: absolute; right: 28rpx; top: 28rpx; font-size: 26rpx; color: #667eea; }

.add-keyword-btn { width: 100%; padding: 32rpx 0; background-color: #f0f0ff; border: 4rpx dashed #667eea; border-radius: 20rpx; color: #667eea; font-size: 30rpx; text-align: center; }
.add-keyword-btn .sub-text { font-size: 24rpx; color: #999; margin-top: 8rpx; }

.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 28rpx 0; border-bottom: 1px solid #f0f0f0; }
.setting-row:last-child { border-bottom: none; }
.setting-row .label { font-size: 30rpx; color: #333; }

.info-box { padding: 24rpx; background-color: #f6f6f6; border-radius: 16rpx; margin-top: 24rpx; }
.info-box .tip { font-size: 26rpx; color: #999; line-height: 1.6; }
</style>