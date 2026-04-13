<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">‹</view>
      <text class="header-title">模型设置</text>
    </view>

    <scroll-view scroll-y class="content-scroll">
      <view class="content-inner">

        <view class="tip-card">
          <text class="tip-icon">ℹ️</text>
          <text class="tip-text">单独为某个 Agent 配置后优先级更高；未配置时自动使用"默认模型"。修改后重启后端生效。</text>
        </view>

        <!-- 默认模型 -->
        <view class="agent-card expanded">
          <view class="agent-header" @click="toggle('default')">
            <view class="agent-meta">
              <view class="agent-name-row">
                <text class="agent-name">默认模型</text>
                <view class="has-key-badge" v-if="agents.default && agents.default.has_key">已配置</view>
                <view class="no-key-badge" v-else>未配置</view>
              </view>
              <text class="agent-role">所有 Agent 的兜底配置，单独配置后优先级更高</text>
            </view>
            <text class="expand-icon">{{ expanded === 'default' ? '−' : '+' }}</text>
          </view>
          <view class="agent-body" v-if="expanded === 'default'">
            <view class="form-row col">
              <text class="form-label">API Key</text>
              <input class="form-input" password placeholder="sk-xxxxxxxx" v-model="forms.default.api_key" />
            </view>
            <view class="form-row col">
              <text class="form-label">Base URL</text>
              <input class="form-input" placeholder="https://api.deepseek.com/v1" v-model="forms.default.base_url" />
            </view>
            <view class="form-row col">
              <text class="form-label">模型名称</text>
              <input class="form-input" placeholder="deepseek-chat" v-model="forms.default.model" />
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('default')">保存</view>
              <view class="test-btn" @click="test('default')">测试连接</view>
            </view>
          </view>
        </view>

        <!-- 分析员 -->
        <view class="agent-card" :class="{ expanded: expanded === 'analyst' }">
          <view class="agent-header" @click="toggle('analyst')">
            <view class="agent-meta">
              <view class="agent-name-row">
                <text class="agent-name">分析员</text>
                <view class="uses-default-badge" v-if="agents.analyst && agents.analyst.uses_default">使用默认</view>
                <view class="has-key-badge" v-else-if="agents.analyst && agents.analyst.has_key">已单独配置</view>
                <view class="no-key-badge" v-else>未配置</view>
              </view>
              <text class="agent-role">舆情风险分析</text>
            </view>
            <text class="expand-icon">{{ expanded === 'analyst' ? '−' : '+' }}</text>
          </view>
          <view class="agent-body" v-if="expanded === 'analyst'">
            <view class="effective-hint" v-if="agents.analyst && agents.analyst.uses_default">
              <text class="hint-text">当前使用默认模型：{{ agents.analyst.effective_model }} · {{ agents.analyst.effective_base_url }}</text>
            </view>
            <view class="form-row col">
              <text class="form-label">API Key <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" password placeholder="sk-xxxxxxxx" v-model="forms.analyst.api_key" />
            </view>
            <view class="form-row col">
              <text class="form-label">Base URL <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="https://api.deepseek.com/v1" v-model="forms.analyst.base_url" />
            </view>
            <view class="form-row col">
              <text class="form-label">模型名称 <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="deepseek-chat" v-model="forms.analyst.model" />
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('analyst')">保存</view>
              <view class="test-btn" @click="test('analyst')">测试连接</view>
            </view>
          </view>
        </view>

        <!-- 复核员 -->
        <view class="agent-card" :class="{ expanded: expanded === 'reviewer' }">
          <view class="agent-header" @click="toggle('reviewer')">
            <view class="agent-meta">
              <view class="agent-name-row">
                <text class="agent-name">复核员</text>
                <view class="uses-default-badge" v-if="agents.reviewer && agents.reviewer.uses_default">使用默认</view>
                <view class="has-key-badge" v-else-if="agents.reviewer && agents.reviewer.has_key">已单独配置</view>
                <view class="no-key-badge" v-else>未配置</view>
              </view>
              <text class="agent-role">交叉复核判定</text>
            </view>
            <text class="expand-icon">{{ expanded === 'reviewer' ? '−' : '+' }}</text>
          </view>
          <view class="agent-body" v-if="expanded === 'reviewer'">
            <view class="effective-hint" v-if="agents.reviewer && agents.reviewer.uses_default">
              <text class="hint-text">当前使用默认模型：{{ agents.reviewer.effective_model }} · {{ agents.reviewer.effective_base_url }}</text>
            </view>
            <view class="form-row col">
              <text class="form-label">API Key <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" password placeholder="sk-xxxxxxxx" v-model="forms.reviewer.api_key" />
            </view>
            <view class="form-row col">
              <text class="form-label">Base URL <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="https://api.moonshot.cn/v1" v-model="forms.reviewer.base_url" />
            </view>
            <view class="form-row col">
              <text class="form-label">模型名称 <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="kimi-k2.5" v-model="forms.reviewer.model" />
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('reviewer')">保存</view>
              <view class="test-btn" @click="test('reviewer')">测试连接</view>
            </view>
          </view>
        </view>

        <!-- 向量引擎 -->
        <view class="agent-card" :class="{ expanded: expanded === 'embedding' }">
          <view class="agent-header" @click="toggle('embedding')">
            <view class="agent-meta">
              <view class="agent-name-row">
                <text class="agent-name">向量引擎</text>
                <view class="uses-default-badge" v-if="agents.embedding && agents.embedding.uses_default">使用默认</view>
                <view class="has-key-badge" v-else-if="agents.embedding && agents.embedding.has_key">已单独配置</view>
                <view class="no-key-badge" v-else>未配置</view>
              </view>
              <text class="agent-role">文本向量聚类</text>
            </view>
            <text class="expand-icon">{{ expanded === 'embedding' ? '−' : '+' }}</text>
          </view>
          <view class="agent-body" v-if="expanded === 'embedding'">
            <view class="effective-hint" v-if="agents.embedding && agents.embedding.uses_default">
              <text class="hint-text">当前使用默认模型：{{ agents.embedding.effective_model }} · {{ agents.embedding.effective_base_url }}</text>
            </view>
            <view class="form-row col">
              <text class="form-label">API Key <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" password placeholder="sk-xxxxxxxx" v-model="forms.embedding.api_key" />
            </view>
            <view class="form-row col">
              <text class="form-label">Base URL <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="https://api.siliconflow.cn/v1" v-model="forms.embedding.base_url" />
            </view>
            <view class="form-row col">
              <text class="form-label">模型名称 <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="BAAI/bge-m3" v-model="forms.embedding.model" />
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('embedding')">保存</view>
              <view class="test-btn" @click="test('embedding')">测试连接</view>
            </view>
          </view>
        </view>

        <!-- 视觉引擎 -->
        <view class="agent-card" :class="{ expanded: expanded === 'vision' }">
          <view class="agent-header" @click="toggle('vision')">
            <view class="agent-meta">
              <view class="agent-name-row">
                <text class="agent-name">视觉引擎</text>
                <view class="uses-default-badge" v-if="agents.vision && agents.vision.uses_default">使用默认</view>
                <view class="has-key-badge" v-else-if="agents.vision && agents.vision.has_key">已单独配置</view>
                <view class="no-key-badge" v-else>未配置</view>
              </view>
              <text class="agent-role">图片证据解析</text>
            </view>
            <text class="expand-icon">{{ expanded === 'vision' ? '−' : '+' }}</text>
          </view>
          <view class="agent-body" v-if="expanded === 'vision'">
            <view class="effective-hint" v-if="agents.vision && agents.vision.uses_default">
              <text class="hint-text">当前使用默认模型：{{ agents.vision.effective_model }} · {{ agents.vision.effective_base_url }}</text>
            </view>
            <view class="form-row col">
              <text class="form-label">API Key <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" password placeholder="sk-xxxxxxxx" v-model="forms.vision.api_key" />
            </view>
            <view class="form-row col">
              <text class="form-label">Base URL <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" v-model="forms.vision.base_url" />
            </view>
            <view class="form-row col">
              <text class="form-label">模型名称 <text class="label-hint">（空则使用默认）</text></text>
              <input class="form-input" placeholder="qwen-vl-max" v-model="forms.vision.model" />
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('vision')">保存</view>
              <view class="test-btn" @click="test('vision')">测试连接</view>
            </view>
          </view>
        </view>

        <view class="page-spacer"></view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getLlmConfigs, updateLlmConfig, testLlmConfig } from '@/utils/api.js'

const goBack = () => uni.navigateBack()

const expanded = ref('default')
const agents = ref({})

const forms = ref({
  default:   { api_key: '', base_url: '', model: '' },
  analyst:   { api_key: '', base_url: '', model: '' },
  reviewer:  { api_key: '', base_url: '', model: '' },
  embedding: { api_key: '', base_url: '', model: '' },
  vision:    { api_key: '', base_url: '', model: '' },
})

const toggle = (agent) => {
  expanded.value = expanded.value === agent ? null : agent
}

const save = async (agent) => {
  const f = forms.value[agent]
  const payload = {}
  if (f.api_key)   payload.api_key = f.api_key
  if (f.base_url) payload.base_url = f.base_url
  if (f.model)    payload.model = f.model
  try {
    const res = await updateLlmConfig(agent, payload)
    uni.showToast({ title: res.code === 200 ? '保存成功' : (res.msg || '保存失败'), icon: res.code === 200 ? 'success' : 'none' })
  } catch (e) {
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

const test = async (agent) => {
  uni.showLoading({ title: '测试中...' })
  try {
    const res = await testLlmConfig(agent)
    uni.hideLoading()
    if (res.code === 200) {
      uni.showToast({ title: '连接成功', icon: 'success' })
    } else {
      uni.showToast({ title: res.msg || '连接失败', icon: 'none' })
    }
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: '连接失败', icon: 'none' })
  }
}

onMounted(async () => {
  uni.showLoading({ title: '加载中...' })
  try {
    const res = await getLlmConfigs()
    uni.hideLoading()
    if (res.code === 200) {
      agents.value = res.data || {}
      for (const [key, cfg] of Object.entries(agents.value)) {
        if (forms.value[key]) {
          forms.value[key].api_key = ''
          forms.value[key].base_url = cfg.base_url || ''
          forms.value[key].model = cfg.model || cfg.default_model || ''
        }
      }
    }
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
})
</script>

<style>
view, text, scroll-view, input, switch { box-sizing: border-box; }
page { background-color: #F8FAFC; }
.page-container { height: 100vh; display: flex; flex-direction: column; background-color: #F8FAFC; }

.header {
  height: 100rpx;
  background-color: #FFFFFF;
  display: flex;
  align-items: center;
  padding: 0 24rpx;
  border-bottom: 1px solid rgba(0,0,0,0.05);
}
.back-btn { font-size: 48rpx; color: #0F172A; margin-right: 24rpx; font-weight: 300; }
.header-title { font-size: 34rpx; font-weight: 600; color: #0F172A; }

.content-scroll { flex: 1; height: 0; }
.content-inner { padding: 24rpx; }

.tip-card {
  background: rgba(8, 145, 178, 0.06);
  border: 1px solid rgba(8, 145, 178, 0.15);
  border-radius: 12rpx;
  padding: 20rpx 24rpx;
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.tip-icon { font-size: 28rpx; flex-shrink: 0; }
.tip-text { font-size: 24rpx; color: #0891B2; line-height: 1.5; }

.agent-card {
  background-color: #FFFFFF;
  border-radius: 16rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 1rpx 3rpx rgba(0,0,0,0.04);
  overflow: hidden;
}
.agent-card.expanded { border: 1px solid #E2E8F0; }

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28rpx;
  cursor: pointer;
}
.agent-meta { display: flex; flex-direction: column; gap: 6rpx; flex: 1; }
.agent-name-row { display: flex; align-items: center; gap: 12rpx; }
.agent-name { font-size: 30rpx; font-weight: 600; color: #0F172A; }
.agent-role { font-size: 22rpx; color: #94A3B8; }

.has-key-badge {
  font-size: 20rpx;
  background: #DCFCE7;
  color: #16A34A;
  padding: 4rpx 12rpx;
  border-radius: 20rpx;
  font-weight: 500;
}
.no-key-badge {
  font-size: 20rpx;
  background: #FEF2F2;
  color: #EF4444;
  padding: 4rpx 12rpx;
  border-radius: 20rpx;
  font-weight: 500;
}
.uses-default-badge {
  font-size: 20rpx;
  background: #EFF6FF;
  color: #3B82F6;
  padding: 4rpx 12rpx;
  border-radius: 20rpx;
  font-weight: 500;
}

.expand-icon { font-size: 40rpx; color: #94A3B8; font-weight: 300; }

.agent-body {
  padding: 0 28rpx 28rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  border-top: 1px solid #F1F5F9;
}

.effective-hint {
  background: #EFF6FF;
  border-radius: 10rpx;
  padding: 16rpx 20rpx;
  margin-top: 4rpx;
}
.hint-text { font-size: 24rpx; color: #3B82F6; word-break: break-all; }

.form-label { font-size: 26rpx; color: #64748B; margin-bottom: 8rpx; }
.label-hint { font-size: 22rpx; color: #94A3B8; }

.form-row { display: flex; align-items: center; gap: 16rpx; }
.form-row.col { flex-direction: column; align-items: flex-start; gap: 8rpx; }
.form-input {
  flex: 1;
  font-size: 28rpx;
  color: #0F172A;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 10rpx;
  padding: 16rpx 20rpx;
  width: 100%;
}

.form-actions { display: flex; gap: 16rpx; padding-top: 8rpx; }
.save-btn {
  flex: 1;
  background-color: #0F172A;
  color: #FFFFFF;
  font-size: 28rpx;
  font-weight: 500;
  text-align: center;
  padding: 20rpx 0;
  border-radius: 12rpx;
}
.test-btn {
  flex: 1;
  background-color: #FFFFFF;
  color: #0F172A;
  font-size: 28rpx;
  font-weight: 500;
  text-align: center;
  padding: 20rpx 0;
  border-radius: 12rpx;
  border: 1px solid #E2E8F0;
}

.page-spacer { height: 60rpx; }
</style>
