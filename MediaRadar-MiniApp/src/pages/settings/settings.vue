<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">‹</view>
      <view class="title">监控设置</view>
      <view class="save-btn" @click="saveSettings">保存生效</view>
    </view>

    <scroll-view scroll-y class="content">
      
      <view class="settings-section">
        <view class="section-header">
          <text class="icon">🎯</text>
          <text class="title">监控关键词</text>
          <text class="count">已添加 {{ settings.keywords.length }}/10</text>
        </view>
        
        <view class="keyword-item" v-for="(kw, index) in settings.keywords" :key="index">
          <view class="keyword-name">{{ kw }}</view>
          <view class="keyword-platforms">
            <text class="platform-check" v-for="pLabel in selectedPlatformLabels" :key="pLabel">☑️ {{ pLabel }}</text>
          </view>
          <view class="edit-btn" @click="removeKeyword(index)">删除</view>
        </view>
        
        <view class="add-keyword-btn" @click="promptAddKeyword">
          <view>+ 添加新关键词</view>
          <view class="sub-text">支持品牌名、高管名、产品名等</view>
        </view>
      </view>

      <view class="settings-section">
        <view class="section-header">
          <text class="icon">🌐</text>
          <text class="title">全局平台抓取设置</text>
        </view>
        
        <view class="setting-row" v-for="plat in platformOptions" :key="plat.val">
          <view class="label">{{ plat.label }}</view>
          <switch 
            :checked="settings.platforms.includes(plat.val)" 
            @change="(e) => togglePlatform(plat.val, e.detail.value)" 
            color="#52c41a" 
            style="transform:scale(0.8)" 
          />
        </view>
      </view>

      <view class="settings-section">
        <view class="section-header">
          <text class="icon">⏱️</text>
          <text class="title">舆情监控自动化</text>
        </view>
        
        <view class="setting-row">
          <view class="label">高风险立刻报警</view>
          <switch 
            :checked="settings.alert_negative" 
            @change="e => settings.alert_negative = e.detail.value" 
            color="#52c41a" 
            style="transform:scale(0.8)" 
          />
        </view>
        
        <view class="setting-row">
          <view class="label">全网扫描频率</view>
          <picker mode="selector" :range="freqOptions" range-key="label" @change="onFreqChange">
            <view class="picker-value">每 {{ settings.monitor_frequency }} 小时 ▾</view>
          </picker>
        </view>
        
        <view class="info-box">
          <view class="tip">开启高风险报警后，当大模型研判出现严重负面时，系统将立刻触发预警机制推送给您。</view>
        </view>
      </view>

      <view class="settings-section">
        <view class="section-header">
          <text class="icon">📅</text>
          <text class="title">每日摘要推送</text>
        </view>
        
        <view class="setting-row">
          <view class="label">开启每日推送</view>
          <switch 
            :checked="settings.push_summary" 
            @change="e => settings.push_summary = e.detail.value" 
            color="#52c41a" 
            style="transform:scale(0.8)" 
          />
        </view>
        
        <view class="setting-row" v-if="settings.push_summary">
          <view class="label">定时推送时间</view>
          <picker mode="time" :value="settings.push_time" @change="e => settings.push_time = e.detail.value">
            <view class="picker-value">{{ settings.push_time }} ▾</view>
          </picker>
        </view>
      </view>

    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const goBack = () => uni.navigateBack()

// 核心配置数据
const settings = ref({
  keywords: [],
  platforms: [],
  push_summary: true,
  push_time: '18:00',
  alert_negative: true,
  monitor_frequency: 1.0
})

// 平台选项定义
const platformOptions = [
  { label: '微博 (Weibo)', val: 'wb', short: '微博' },
  { label: '小红书 (Xiaohongshu)', val: 'xhs', short: '小红书' },
  { label: '抖音 (Douyin)', val: 'dy', short: '抖音' },
  { label: '知乎 (Zhihu)', val: 'zhihu', short: '知乎' },
  { label: 'B站 (Bilibili)', val: 'bili', short: 'B站' },
  { label: '贴吧 (Tieba)', val: 'tieba', short: '贴吧' },
  { label: '快手 (Kuaishou)', val: 'ks', short: '快手' }
]

const freqOptions = [
  { label: '每 0.5 小时', val: 0.5 },
  { label: '每 1 小时', val: 1.0 },
  { label: '每 1.5 小时', val: 1.5 },
  { label: '每 2 小时', val: 2.0 },
  { label: '每 4 小时', val: 4.0 },
  { label: '每 12 小时', val: 12.0 },
  { label: '每 24 小时', val: 24.0 }
]

// 动态计算在关键词卡片上显示的平台简称
const selectedPlatformLabels = computed(() => {
  return platformOptions
    .filter(p => settings.value.platforms.includes(p.val))
    .map(p => p.short)
})

// ---------------- 操作逻辑 ----------------

// 添加关键词（调起原生输入弹窗）
const promptAddKeyword = () => {
  uni.showModal({
    title: '添加监控关键词',
    editable: true,
    placeholderText: '请输入品牌名/高管名等',
    success: (res) => {
      if (res.confirm && res.content.trim()) {
        const kw = res.content.trim()
        if (!settings.value.keywords.includes(kw)) {
          settings.value.keywords.push(kw)
        } else {
          uni.showToast({ title: '关键词已存在', icon: 'none' })
        }
      }
    }
  })
}

// 删除关键词
const removeKeyword = (index) => {
  settings.value.keywords.splice(index, 1)
}

// 切换平台抓取开关
const togglePlatform = (val, isChecked) => {
  if (isChecked) {
    if (!settings.value.platforms.includes(val)) settings.value.platforms.push(val)
  } else {
    settings.value.platforms = settings.value.platforms.filter(p => p !== val)
  }
}

// 更改监控频率
const onFreqChange = (e) => {
  const selected = freqOptions[e.detail.value]
  settings.value.monitor_frequency = selected.val
}

// ---------------- 网络请求 ----------------

// 初始化加载设置
const loadSettings = () => {
  uni.showLoading({ title: '加载中...' })
  uni.request({
    url: 'http://127.0.0.1:8000/api/settings',
    method: 'GET',
    success: (res) => {
      uni.hideLoading()
      if (res.data && res.data.code === 200) {
        settings.value = res.data.data
      }
    },
    fail: () => {
      uni.hideLoading()
      uni.showToast({ title: '拉取配置失败', icon: 'none' })
    }
  })
}

// 保存设置并使其立刻生效
const saveSettings = () => {
  if (settings.value.keywords.length === 0) {
    return uni.showToast({ title: '至少保留一个关键词', icon: 'none' })
  }
  if (settings.value.platforms.length === 0) {
    return uni.showToast({ title: '至少选择一个平台', icon: 'none' })
  }

  uni.showLoading({ title: '正在生效...' })
  uni.request({
    url: 'http://127.0.0.1:8000/api/settings',
    method: 'POST',
    data: settings.value,
    success: (res) => {
      uni.hideLoading()
      if (res.data && res.data.code === 200) {
        uni.showToast({ title: '规则已全局生效', icon: 'success' })
        setTimeout(() => goBack(), 1200)
      }
    },
    fail: () => {
      uni.hideLoading()
      uni.showToast({ title: '保存失败，请检查网络', icon: 'none' })
    }
  })
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #f5f5f5; }
.header { height: 100rpx; background-color: #ffffff; display: flex; justify-content: space-between; align-items: center; padding: 0 32rpx; border-bottom: 2rpx solid #eee; z-index: 10; }
.header .back-btn { font-size: 50rpx; color: #333; cursor: pointer; width: 60rpx; margin-top: -10rpx;}
.header .title { font-size: 36rpx; font-weight: 600; color: #333; }
.header .save-btn { font-size: 26rpx; color: #fff; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 10rpx 24rpx; border-radius: 30rpx; font-weight: 500;}

.content { flex: 1; padding: 32rpx; box-sizing: border-box; }

.settings-section { background-color: #fff; border-radius: 24rpx; padding: 32rpx; margin-bottom: 24rpx; box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.02);}
.section-header { display: flex; align-items: center; margin-bottom: 32rpx; }
.section-header .icon { font-size: 40rpx; margin-right: 16rpx; }
.section-header .title { font-size: 32rpx; font-weight: 600; color: #333; }
.section-header .count { margin-left: auto; font-size: 26rpx; color: #667eea; }

.keyword-item { padding: 28rpx; background-color: #f9f9f9; border-radius: 20rpx; margin-bottom: 20rpx; position: relative;}
.keyword-name { font-size: 30rpx; font-weight: 600; color: #333; margin-bottom: 16rpx; }
.keyword-platforms { display: flex; flex-wrap: wrap; gap: 16rpx; }
.platform-check { font-size: 24rpx; color: #666; background: #fff; padding: 4rpx 16rpx; border-radius: 12rpx; border: 1px solid #eee;}
.edit-btn { position: absolute; right: 28rpx; top: 28rpx; font-size: 26rpx; color: #ff4d4f; font-weight: 500; padding: 10rpx; }

.add-keyword-btn { width: 100%; padding: 32rpx 0; background-color: #f0f0ff; border: 4rpx dashed #667eea; border-radius: 20rpx; color: #667eea; font-size: 30rpx; text-align: center; font-weight: 500;}
.add-keyword-btn .sub-text { font-size: 24rpx; color: #999; margin-top: 8rpx; font-weight: normal;}

.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 28rpx 0; border-bottom: 1px solid #f0f0f0; }
.setting-row:last-child { border-bottom: none; }
.setting-row .label { font-size: 30rpx; color: #333; }
.picker-value { font-size: 30rpx; color: #667eea; font-weight: 500; }

.info-box { padding: 24rpx; background-color: #f8f8f8; border-radius: 16rpx; margin-top: 24rpx; border-left: 6rpx solid #52c41a; }
.info-box .tip { font-size: 26rpx; color: #888; line-height: 1.6; }
</style>