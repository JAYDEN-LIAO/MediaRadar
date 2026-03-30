<template>
  <view class="page-container">
    <view class="header">
      <view class="title">监控设置</view>
    </view>

    <scroll-view scroll-y class="content-scroll">
      <view class="content-inner">
        
        <view class="settings-card">
          <view class="card-header">
            <view class="header-left">
              <text class="icon">🎯</text>
              <text class="title">监控关键词</text>
            </view>
            <text class="count-tag">{{ activeKeywords.filter(k => k.active).length }}/10</text>
          </view>
          
          <view class="keyword-list">
            <view 
              class="keyword-item" 
              v-for="(item, index) in activeKeywords" 
              :key="index"
              :class="{ 'is-inactive': !item.active }"
            >
              <view class="kw-main">
                <view class="kw-info">
                  <text class="kw-name">{{ item.text }}</text>
                  <text class="kw-status" :class="item.active ? 'status-on' : 'status-off'">
                    {{ item.active ? '监控中' : '已停用' }}
                  </text>
                </view>
                
                <view class="kw-levels" v-if="item.active">
                  <text class="level-label">监控等级:</text>
                  <view class="level-options">
                    <text class="level-tag" :class="{'active-conservative': item.level === 'conservative'}" @click="setKwLevel(index, 'conservative')">保守</text>
                    <text class="level-tag" :class="{'active-balanced': item.level === 'balanced'}" @click="setKwLevel(index, 'balanced')">平衡</text>
                    <text class="level-tag" :class="{'active-aggressive': item.level === 'aggressive'}" @click="setKwLevel(index, 'aggressive')">激进</text>
                  </view>
                </view>
              </view>

              <view class="kw-actions">
                <switch 
                  :checked="item.active" 
                  @change="(e) => toggleKeyword(index, e.detail.value)" 
                  color="#4F46E5" 
                  style="transform:scale(0.8)"
                />
                <view class="delete-btn" @click="removeKeyword(index)">🗑️</view>
              </view>
            </view>
            
            <view class="add-keyword-btn" @click="promptAddKeyword">
              <text class="add-icon">+</text> 添加新监控词
            </view>
          </view>
        </view>

        <view class="settings-card">
          <view class="card-header">
            <view class="header-left">
              <text class="icon">🌐</text>
              <text class="title">数据源平台</text>
            </view>
            <text class="count-tag">{{ settings.platforms.length }}/{{ platformOptions.length }}</text>
          </view>
          <view class="platform-grid">
            <view 
              class="platform-item" 
              v-for="(plat, index) in platformOptions" 
              :key="index"
              :class="{ 'is-active': settings.platforms.includes(plat.val) }"
              @click="togglePlatform(plat.val, !settings.platforms.includes(plat.val))"
            >
              {{ plat.label }}
            </view>
          </view>
        </view>

        <view class="settings-card">
          <view class="card-header">
            <view class="header-left">
              <text class="icon">⚙️</text>
              <text class="title">预警与调度</text>
            </view>
          </view>
          
          <view class="setting-row">
            <view class="row-left">
              <text class="row-title">负面舆情立即预警</text>
              <text class="row-desc">发现高危负面时直接推送通知</text>
            </view>
            <switch :checked="settings.alert_negative" @change="e => settings.alert_negative = e.detail.value" color="#EF4444" style="transform:scale(0.8)"/>
          </view>
          
          <view class="setting-row">
            <view class="row-left">
              <text class="row-title">每日简报推送</text>
              <text class="row-desc">汇总全天舆情态势及 AI 分析</text>
            </view>
            <switch :checked="settings.push_summary" @change="e => settings.push_summary = e.detail.value" color="#10B981" style="transform:scale(0.8)"/>
          </view>
          
          <view class="setting-row" v-if="settings.push_summary">
            <view class="row-left">
              <text class="row-title">简报推送时间</text>
            </view>
            <picker mode="time" :value="settings.push_time" @change="e => settings.push_time = e.detail.value">
              <view class="picker-value">{{ settings.push_time }} ▾</view>
            </picker>
          </view>
          
          <view class="setting-row" style="border-bottom: none;">
            <view class="row-left">
              <text class="row-title">自动监控频率</text>
            </view>
            <picker 
              mode="selector" 
              :range="freqOptions" 
              range-key="label" 
              @change="onFreqChange"
            >
              <view class="picker-value">
                {{ freqOptions.find(opt => opt.val === settings.monitor_frequency)?.label || '请选择' }} ▾
              </view>
            </picker>
          </view>
        </view>
        
        <view class="safe-area-bottom"></view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const goBack = () => uni.navigateBack()

// 核心配置数据
const settings = ref({
  platforms: [],
  push_summary: true,
  push_time: '18:00',
  alert_negative: true,
  monitor_frequency: 1.0
})

const activeKeywords = ref([])

// 平台选项
const platformOptions = [
  { label: '微博', val: 'wb' },
  { label: '小红书', val: 'xhs' },
  { label: '抖音', val: 'dy' },
  { label: '知乎', val: 'zhihu' },
  { label: 'B站', val: 'bili' }
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

// ---------------- 自动保存逻辑 ----------------
let isLoaded = false
let saveTimer = null

const triggerAutoSave = () => {
  if (!isLoaded) return
  if (saveTimer) clearTimeout(saveTimer)
  
  saveTimer = setTimeout(() => {
    executeSaveSilent()
  }, 800)
}

const executeSaveSilent = () => {
  const activeCount = activeKeywords.value.filter(k => k.active).length
  if (activeCount === 0) {
    uni.showToast({ title: '警告：请至少保留一个开启的监控词', icon: 'none' })
    return
  }
  if (settings.value.platforms.length === 0) {
    uni.showToast({ title: '警告：至少选择一个抓取平台', icon: 'none' })
    return
  }

  // ✨ 核心修改：现在传给后端的是带 level 的对象数组，不再是纯字符串
  const payload = {
    ...settings.value,
    keywords: activeKeywords.value.filter(k => k.active).map(k => ({ text: k.text, level: k.level })),
    inactive_keywords: activeKeywords.value.filter(k => !k.active).map(k => ({ text: k.text, level: k.level }))
  }

  uni.request({
    url: 'http://127.0.0.1:8008/api/settings',
    method: 'POST',
    data: payload,
    success: (res) => {
      if (res.data && res.data.code === 200) {
        console.log('配置已自动保存生效', payload)
      }
    }
  })
}

watch(settings, () => { triggerAutoSave() }, { deep: true })
watch(activeKeywords, () => { triggerAutoSave() }, { deep: true })


// ---------------- 操作逻辑 ----------------

const promptAddKeyword = () => {
  uni.showModal({
    title: '添加监控目标',
    editable: true,
    placeholderText: '请输入品牌名/产品名等',
    success: (res) => {
      if (res.confirm && res.content.trim()) {
        const kw = res.content.trim()
        const exists = activeKeywords.value.find(item => item.text === kw)
        if (!exists) {
          // ✨ 新增词汇默认等级为“平衡 (balanced)”
          activeKeywords.value.push({ text: kw, active: true, level: 'balanced' })
        } else {
          uni.showToast({ title: '关键词已存在', icon: 'none' })
        }
      }
    }
  })
}

const toggleKeyword = (index, val) => {
  activeKeywords.value[index].active = val
}

// ✨ 新增：设置关键词监控等级
const setKwLevel = (index, level) => {
  activeKeywords.value[index].level = level
}

const removeKeyword = (index) => {
  activeKeywords.value.splice(index, 1)
}

const togglePlatform = (val, isChecked) => {
  if (isChecked) {
    if (!settings.value.platforms.includes(val)) settings.value.platforms.push(val)
  } else {
    settings.value.platforms = settings.value.platforms.filter(p => p !== val)
  }
}

const onFreqChange = (e) => {
  const selected = freqOptions[e.detail.value]
  settings.value.monitor_frequency = selected.val
}

// ---------------- 网络请求 ----------------

const loadSettings = () => {
  uni.showLoading({ title: '加载中...' })
  uni.request({
    url: 'http://127.0.0.1:8008/api/settings',
    method: 'GET',
    success: (res) => {
      uni.hideLoading()
      if (res.data && res.data.code === 200) {
        const data = res.data.data
        settings.value = { ...data }
        
        const kwActive = data.keywords || []
        const kwInactive = data.inactive_keywords || []
        
        activeKeywords.value = [
          ...kwActive.map(k => typeof k === 'string' ? { text: k, active: true, level: 'balanced' } : { text: k.text, active: true, level: k.level || 'balanced' }),
          ...kwInactive.map(k => typeof k === 'string' ? { text: k, active: false, level: 'balanced' } : { text: k.text, active: false, level: k.level || 'balanced' })
        ]
        
        setTimeout(() => { isLoaded = true }, 500)
      }
    },
    fail: () => {
      uni.hideLoading()
      uni.showToast({ title: '拉取配置失败', icon: 'none' })
    }
  })
}

onMounted(() => {
  loadSettings()
})
</script>

<style>
view, text, scroll-view, picker, input {
  box-sizing: border-box;
}
page { background-color: #F4F5F7; }
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #F4F5F7; }

.header { 
  height: 100rpx;  /* 固定的矮高度 */
  background-color: rgba(255, 255, 255, 0.9); /* 开启半透明 */
  backdrop-filter: blur(10px); /* 开启磨砂玻璃效果 */
  display: flex; 
  justify-content: center; /* 这里改为 center，严格居中 */
  align-items: center; 
  padding: 0 32rpx; 
  border-bottom: 1px solid rgba(0,0,0,0.05); 
  z-index: 10; 
}

.header .title { 
  font-size: 34rpx; 
  font-weight: 600; 
  color: #111827; 
  letter-spacing: 1rpx; /* 增加一点字间距，更有质感 */
}

.content-scroll { flex: 1; height: 0; }
.content-inner { padding: 24rpx; }

.settings-card { background-color: #fff; border-radius: 24rpx; padding: 32rpx; margin-bottom: 24rpx; box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.02); }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32rpx; }
.header-left { display: flex; align-items: center; }
.header-left .icon { font-size: 36rpx; margin-right: 16rpx; }
.header-left .title { font-size: 30rpx; font-weight: 600; color: #111827; }
.count-tag { font-size: 24rpx; color: #6B7280; background-color: #F3F4F6; padding: 4rpx 16rpx; border-radius: 20rpx;}

/* 关键词列表样式更新 */
.keyword-list { display: flex; flex-direction: column; gap: 20rpx; }
.keyword-item { display: flex; justify-content: space-between; align-items: center; padding: 24rpx; background-color: #F9FAFB; border-radius: 16rpx; border: 1px solid #F3F4F6; transition: all 0.3s;}
.keyword-item.is-inactive { opacity: 0.6; background-color: #F3F4F6; }

.kw-main { flex: 1; display: flex; flex-direction: column; gap: 12rpx; }
.kw-info { display: flex; align-items: center; gap: 16rpx; }
.kw-name { font-size: 30rpx; font-weight: 600; color: #111827; }
.kw-status { font-size: 22rpx; font-weight: 500;}
.status-on { color: #10B981; }
.status-off { color: #9CA3AF; }

/* 敏感度等级标签样式 */
.kw-levels { display: flex; align-items: center; gap: 16rpx; margin-top: 4rpx; }
.level-label { font-size: 22rpx; color: #6B7280; }
.level-options { display: flex; background: #E5E7EB; border-radius: 8rpx; padding: 4rpx; gap: 4rpx;}
.level-tag { font-size: 20rpx; padding: 6rpx 20rpx; border-radius: 6rpx; color: #6B7280; transition: all 0.2s ease; font-weight: 500;}
.active-conservative { background: #10B981; color: #fff; box-shadow: 0 2rpx 4rpx rgba(16,185,129,0.3);}
.active-balanced { background: #3B82F6; color: #fff; box-shadow: 0 2rpx 4rpx rgba(59,130,246,0.3);}
.active-aggressive { background: #EF4444; color: #fff; box-shadow: 0 2rpx 4rpx rgba(239,68,68,0.3);}

.kw-actions { display: flex; align-items: center; gap: 16rpx; }
.delete-btn { font-size: 24rpx; color: #EF4444; padding: 12rpx; }

.add-keyword-btn { width: 100%; padding: 28rpx 0; background-color: rgba(79, 70, 229, 0.04); border-radius: 16rpx; color: #4F46E5; font-size: 28rpx; display: flex; justify-content: center; align-items: center; font-weight: 500; margin-top: 8rpx;}
.add-icon { font-size: 36rpx; margin-right: 8rpx; margin-top: -4rpx;}

/* 其他原有样式保留 */
.platform-grid { display: flex; flex-wrap: wrap; gap: 16rpx; }
.platform-item { padding: 16rpx 28rpx; background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 100rpx; font-size: 26rpx; color: #4B5563; transition: all 0.2s; }
.platform-item.is-active { background-color: #4F46E5; color: #fff; border-color: #4F46E5; font-weight: 500; }

.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 32rpx 0; border-bottom: 1px solid #F3F4F6; }
.row-left { display: flex; flex-direction: column; gap: 8rpx; }
.row-title { font-size: 28rpx; font-weight: 500; color: #111827; }
.row-desc { font-size: 24rpx; color: #9CA3AF; }
.picker-value { font-size: 28rpx; color: #4F46E5; font-weight: 500; background-color: rgba(79, 70, 229, 0.05); padding: 12rpx 24rpx; border-radius: 12rpx; }

.safe-area-bottom { height: 60rpx; }
</style>