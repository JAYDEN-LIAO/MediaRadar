<template>
  <view class="page-container">
    <view class="profile-header">
      <view class="avatar">🧑‍💻</view>
      <view class="nickname">管理员用户</view>
    </view>

    <view class="content-no-tab">
      <view class="stats-card">
        <view class="stat">
          <view class="number">128</view>
          <view class="label">累计扫描</view>
        </view>
        <view class="stat">
          <view class="number">15</view>
          <view class="label">已处理预警</view>
        </view>
        <view class="stat" style="border-right: none;">
          <view class="number">99%</view>
          <view class="label">系统健康度</view>
        </view>
      </view>

      <view class="menu-list">
        <view class="menu-item">
          <text class="icon">📄</text>
          <text class="label">导出数据报表</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item">
          <text class="icon">🔑</text>
          <text class="label">大模型 API 设置</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item" @click="goToSettings">
          <text class="icon">⚙️</text>
          <text class="label">系统偏好设置</text>
          <text class="arrow">›</text>
        </view>
        <view class="menu-item">
          <text class="icon">🎧</text>
          <text class="label">联系技术支持</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <view class="version-info">舆情雷达 V2.0.0 · 当前为最新版本</view>
    </view>
  </view>
</template>

<script setup>
const goToSettings = () => uni.navigateTo({ url: '/pages/settings/settings' })
</script>

<style scoped>
.profile-header {
  text-align: center;
  padding: 80rpx 32rpx 60rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 0 0 60rpx 60rpx;
  /* 填补自定义导航栏的顶部空隙 */
  padding-top: calc(80rpx + var(--status-bar-height)); 
}
.profile-header .avatar {
  width: 160rpx;
  height: 160rpx;
  background-color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 80rpx;
  margin: 0 auto 24rpx;
  box-shadow: 0 8rpx 30rpx rgba(0, 0, 0, 0.2);
}
.profile-header .nickname { font-size: 36rpx; font-weight: 600; color: #fff; }

.content-no-tab { padding: 32rpx; margin-top: -60rpx; position: relative; z-index: 10; }

.stats-card { display: flex; background-color: #fff; border-radius: 24rpx; padding: 40rpx 0; margin-bottom: 24rpx; box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.05); }
.stats-card .stat { flex: 1; text-align: center; border-right: 1px solid #f0f0f0; }
.stats-card .stat .number { font-size: 48rpx; font-weight: 700; color: #667eea; }
.stats-card .stat .label { font-size: 24rpx; color: #999; margin-top: 8rpx; }

.menu-list { background-color: #fff; border-radius: 24rpx; overflow: hidden; box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.05);}
.menu-item { display: flex; align-items: center; padding: 32rpx; border-bottom: 1px solid #f0f0f0; }
.menu-item:last-child { border-bottom: none; }
.menu-item .icon { font-size: 40rpx; margin-right: 24rpx; }
.menu-item .label { flex: 1; font-size: 30rpx; color: #333; }
.menu-item .arrow { font-size: 32rpx; color: #ccc; }

.version-info { text-align: center; padding: 40rpx; color: #999; font-size: 26rpx; }
</style>