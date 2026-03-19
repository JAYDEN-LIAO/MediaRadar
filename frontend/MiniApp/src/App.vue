<script>
export default {
  onLaunch: function () { console.log('App Launch') },
  onShow: function () { console.log('App Show') },
  onHide: function () { console.log('App Hide') },
}
</script>

<style>
/* 全局基础样式 */
page {
  background-color: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  color: #333;
}

/* 隐藏滚动条 */
::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
  color: transparent;
}

/* 通用头部样式 (替代微信默认导航栏) */
.header {
  height: 100rpx;
  background-color: #ffffff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32rpx;
  /* 如果是在真机上，建议加上状态栏高度的 padding-top */
  padding-top: var(--status-bar-height); 
}
.header .title {
  font-size: 36rpx;
  font-weight: 600;
  color: #333;
}
.header .back-btn, .header .action-btn {
  font-size: 40rpx;
  color: #333;
  width: 60rpx;
  text-align: center;
  cursor: pointer;
}

/* 通用卡片样式 */
.card {
  background-color: #ffffff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.05);
}
.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 32rpx;
}
.card-header .icon {
  font-size: 40rpx;
  margin-right: 16rpx;
}
.card-header .title {
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
}
</style>