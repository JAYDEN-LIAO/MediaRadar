<template>
  <view class="page-container">
    <view class="profile-header">
      <view class="avatar">
        <view class="avatar-inner"></view>
      </view>
      <view class="nickname">管理员用户</view>
    </view>

    <view class="content">
      <view class="menu-list">
        <view class="menu-item" @click="goToPushSettings">
          <text class="label">推送设置</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item" @click="goToApiSettings">
          <text class="label">模型设置</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item" @click="copyEmail">
          <text class="label">联系我们</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <view class="version-info">舆情雷达 V1.0.1</view>
    </view>
  </view>
</template>

<script setup>
const goToPushSettings = () => uni.navigateTo({ url: '/pages/settings/pushSettings' })
const goToApiSettings = () => uni.navigateTo({ url: '/pages/settings/apiSettings' })
const copyEmail = () => {
  uni.setClipboardData({
    data: 'jaydenliao1027@gmail.com',
    success: () => uni.showToast({ title: '已复制邮箱', icon: 'success' }),
    fail: () => uni.showToast({ title: '复制失败', icon: 'none' }),
  })
}
</script>

<style scoped>
.page-container {
  min-height: 100vh;
  background-color: #F8FAFC;
}

.profile-header {
  text-align: center;
  padding: 80rpx 32rpx 64rpx;
  background-color: #0F172A;
  border-radius: 0 0 48rpx 48rpx;
  padding-top: calc(80rpx + var(--status-bar-height));
}

.profile-header .avatar {
  width: 140rpx;
  height: 140rpx;
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.2);
}

.avatar-inner {
  width: 80rpx;
  height: 80rpx;
  background: repeating-linear-gradient(
    45deg,
    rgba(255,255,255,0.8) 0rpx,
    rgba(255,255,255,0.8) 2rpx,
    transparent 2rpx,
    transparent 8rpx
  );
  border-radius: 50%;
}

.profile-header .nickname {
  font-size: 36rpx;
  font-weight: 600;
  color: #FFFFFF;
  letter-spacing: 2rpx;
}

.content {
  padding: 32rpx 24rpx;
}

.menu-list {
  background-color: #FFFFFF;
  border-radius: 16rpx;
  overflow: hidden;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx 28rpx;
  border-bottom: 1rpx solid #F1F5F9;
  transition: background-color 0.15s ease;
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-item:active {
  background-color: #F8FAFC;
}

.menu-item .label {
  font-size: 30rpx;
  color: #334155;
}

.menu-item .arrow {
  font-size: 32rpx;
  color: #CBD5E1;
  font-weight: 300;
}

.version-info {
  text-align: center;
  padding: 48rpx 0 32rpx;
  color: #94A3B8;
  font-size: 24rpx;
  font-family: 'JetBrains Mono', monospace;
}
</style>
