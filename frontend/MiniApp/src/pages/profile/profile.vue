<template>
  <view class="page-container">
    <view class="profile-header">
      <view class="avatar">
        <view class="avatar-inner"></view>
      </view>
      <view class="nickname">管理员用户</view>
    </view>

    <view class="content">
      <view class="stats-card">
        <view class="stat">
          <view class="number">128</view>
          <view class="label">累计扫描</view>
        </view>
        <view class="stat-divider"></view>
        <view class="stat">
          <view class="number">15</view>
          <view class="label">已处理预警</view>
        </view>
        <view class="stat-divider"></view>
        <view class="stat">
          <view class="number">99<span class="unit">%</span></view>
          <view class="label">系统健康度</view>
        </view>
      </view>

      <view class="menu-list">
        <view class="menu-item">
          <text class="label">导出数据报表</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item">
          <text class="label">大模型 API 设置</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item" @click="goToSettings">
          <text class="label">系统偏好设置</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item">
          <text class="label">联系技术支持</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <view class="version-info">舆情雷达 V2.0.0</view>
    </view>
  </view>
</template>

<script setup>
const goToSettings = () => uni.navigateTo({ url: '/pages/settings/settings' })
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
  margin-top: -40rpx;
  position: relative;
  z-index: 10;
}

.stats-card {
  display: flex;
  align-items: center;
  background-color: #FFFFFF;
  border-radius: 16rpx;
  padding: 40rpx 0;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.stats-card .stat {
  flex: 1;
  text-align: center;
  position: relative;
}

.stats-card .stat .number {
  font-size: 52rpx;
  font-weight: 700;
  color: #0F172A;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  line-height: 1.1;
}

.stats-card .stat .unit {
  font-size: 32rpx;
  font-weight: 500;
}

.stats-card .stat .label {
  font-size: 24rpx;
  color: #64748B;
  margin-top: 8rpx;
}

.stat-divider {
  width: 1rpx;
  height: 60rpx;
  background-color: #E2E8F0;
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
