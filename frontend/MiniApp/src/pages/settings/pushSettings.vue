<template>
  <view class="page-container">
    <view class="header">
      <view class="back-btn" @click="goBack">‹</view>
      <text class="header-title">推送设置</text>
    </view>

    <scroll-view scroll-y class="content-scroll">
      <view class="content-inner">

        <!-- 企业微信 -->
        <view class="channel-card">
          <view class="channel-header">
            <view class="channel-meta">
              <text class="channel-name">企业微信</text>
              <text class="channel-hint">Webhook 机器人推送</text>
            </view>
            <switch :checked="configs.wecom.enabled" @change="e => update('wecom', 'enabled', e.detail.value)" color="#07C160"/>
          </view>

          <view class="channel-body" v-if="configs.wecom.enabled">
            <view class="form-row">
              <text class="form-label">触发等级</text>
              <view class="level-tags">
                <text v-for="lv in [1,2,3,4,5]" :key="lv"
                  class="level-tag"
                  :class="{ active: configs.wecom.risk_min_level === lv }"
                  @click="update('wecom', 'risk_min_level', lv)">
                  {{ lv }}级
                </text>
              </view>
            </view>
            <view class="form-row col">
              <text class="form-label">Webhook 地址</text>
              <input class="form-input" placeholder="https://qyapi.weixin.qq.com/..." v-model="configs.wecom.webhook_url" @blur="save('wecom')"/>
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('wecom')">保存</view>
              <view class="test-btn" @click="test('wecom')">发送测试</view>
            </view>
          </view>
        </view>

        <!-- 飞书 -->
        <view class="channel-card">
          <view class="channel-header">
            <view class="channel-meta">
              <text class="channel-name">飞书</text>
              <text class="channel-hint">Webhook 机器人推送</text>
            </view>
            <switch :checked="configs.feishu.enabled" @change="e => update('feishu', 'enabled', e.detail.value)" color="#1989FA"/>
          </view>

          <view class="channel-body" v-if="configs.feishu.enabled">
            <view class="form-row">
              <text class="form-label">触发等级</text>
              <view class="level-tags">
                <text v-for="lv in [1,2,3,4,5]" :key="lv"
                  class="level-tag"
                  :class="{ active: configs.feishu.risk_min_level === lv }"
                  @click="update('feishu', 'risk_min_level', lv)">
                  {{ lv }}级
                </text>
              </view>
            </view>
            <view class="form-row col">
              <text class="form-label">Webhook 地址</text>
              <input class="form-input" placeholder="https://open.feishu.cn/open-apis/bot/v2/..." v-model="configs.feishu.webhook_url" @blur="save('feishu')"/>
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('feishu')">保存</view>
              <view class="test-btn" @click="test('feishu')">发送测试</view>
            </view>
          </view>
        </view>

        <!-- 邮箱 -->
        <view class="channel-card">
          <view class="channel-header">
            <view class="channel-meta">
              <text class="channel-name">邮箱</text>
              <text class="channel-hint">SMTP 邮件推送</text>
            </view>
            <switch :checked="configs.email.enabled" @change="e => update('email', 'enabled', e.detail.value)" color="#EA4335"/>
          </view>

          <view class="channel-body" v-if="configs.email.enabled">
            <view class="form-row">
              <text class="form-label">触发等级</text>
              <view class="level-tags">
                <text v-for="lv in [1,2,3,4,5]" :key="lv"
                  class="level-tag"
                  :class="{ active: configs.email.risk_min_level === lv }"
                  @click="update('email', 'risk_min_level', lv)">
                  {{ lv }}级
                </text>
              </view>
            </view>
            <view class="form-row col">
              <text class="form-label">SMTP 服务器</text>
              <input class="form-input" placeholder="smtp.example.com" v-model="configs.email.smtp_host" @blur="save('email')"/>
            </view>
            <view class="form-row">
              <text class="form-label">端口</text>
              <input class="form-input short" type="number" placeholder="587" v-model="configs.email.smtp_port" @blur="save('email')"/>
              <view class="form-switch">
                <text class="switch-label">TLS</text>
                <switch :checked="configs.email.smtp_use_tls" @change="e => update('email', 'smtp_use_tls', e.detail.value)" color="#EA4335"/>
              </view>
            </view>
            <view class="form-row col">
              <text class="form-label">用户名</text>
              <input class="form-input" placeholder="your@email.com" v-model="configs.email.smtp_user" @blur="save('email')"/>
            </view>
            <view class="form-row col">
              <text class="form-label">密码/授权码</text>
              <input class="form-input" password placeholder="请输入密码或授权码" v-model="configs.email.smtp_password" @blur="save('email')"/>
            </view>
            <view class="form-row col">
              <text class="form-label">发件人</text>
              <input class="form-input" placeholder="alarm@example.com" v-model="configs.email.from_addr" @blur="save('email')"/>
            </view>
            <view class="form-row col">
              <text class="form-label">收件人（多个用逗号分隔）</text>
              <input class="form-input" placeholder="admin@example.com,ops@example.com" v-model="emailToAddrs" @blur="saveEmailToAddrs()"/>
            </view>
            <view class="form-actions">
              <view class="save-btn" @click="save('email')">保存</view>
              <view class="test-btn" @click="test('email')">发送测试</view>
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
import { getPushConfigs, savePushConfig, testPushChannel } from '@/utils/api.js'

const goBack = () => uni.navigateBack()

const configs = ref({
  email: { enabled: false, risk_min_level: 3, smtp_host: '', smtp_port: 587, smtp_user: '', smtp_password: '', smtp_use_tls: true, from_addr: '', to_addrs: [], webhook_url: '' },
  wecom: { enabled: false, risk_min_level: 2, webhook_url: '' },
  feishu: { enabled: false, risk_min_level: 2, webhook_url: '' },
})

let emailToAddrs = ''

const update = (channel, field, value) => {
  configs.value[channel][field] = value
  if (channel === 'email' && field === 'enabled' && value) {
    // 启用时自动加载完整配置
    loadFullConfig('email')
  }
}

const loadFullConfig = async (channel) => {
  try {
    const res = await getPushConfig(channel)
    if (res.code === 200) {
      const data = res.data
      if (channel === 'email') {
        data.smtp_password = ''
        configs.value.email = { ...configs.value.email, ...data }
        emailToAddrs = (data.to_addrs || []).join(',')
      } else {
        configs.value[channel] = { ...configs.value[channel], ...data }
      }
    }
  } catch (e) {
    console.error('加载配置失败', e)
  }
}

const save = async (channel) => {
  let payload = { ...configs.value[channel] }
  if (channel === 'email') {
    payload.to_addrs = emailToAddrs.split(',').map(s => s.trim()).filter(Boolean)
  }
  try {
    const res = await savePushConfig(channel, payload)
    if (res.code === 200) {
      uni.showToast({ title: '保存成功', icon: 'success' })
    } else {
      uni.showToast({ title: res.msg || '保存失败', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

const saveEmailToAddrs = () => {
  configs.value.email.to_addrs = emailToAddrs.split(',').map(s => s.trim()).filter(Boolean)
}

const test = async (channel) => {
  // 先保存
  await save(channel)
  if (!configs.value[channel].enabled) {
    uni.showToast({ title: '请先启用通道', icon: 'none' })
    return
  }
  uni.showLoading({ title: '发送中...' })
  try {
    const res = await testPushChannel(channel)
    uni.hideLoading()
    if (res.code === 200) {
      uni.showToast({ title: '测试发送成功', icon: 'success' })
    } else {
      uni.showToast({ title: res.msg || '发送失败', icon: 'none' })
    }
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: '网络错误', icon: 'none' })
  }
}

onMounted(async () => {
  uni.showLoading({ title: '加载中...' })
  try {
    const res = await getPushConfigs()
    uni.hideLoading()
    if (res.code === 200) {
      const data = res.data || {}
      // 只展示简洁信息（无密码）
      if (data.email) {
        configs.value.email = { ...configs.value.email, ...data.email, smtp_password: '' }
        emailToAddrs = (data.email.to_addrs || []).join(',')
      }
      if (data.wecom) configs.value.wecom = { ...configs.value.wecom, ...data.wecom }
      if (data.feishu) configs.value.feishu = { ...configs.value.feishu, ...data.feishu }
    }
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: '加载配置失败', icon: 'none' })
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

.channel-card {
  background-color: #FFFFFF;
  border-radius: 16rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 1rpx 3rpx rgba(0,0,0,0.04);
  overflow: hidden;
}
.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28rpx;
  border-bottom: 1px solid #F1F5F9;
}
.channel-meta { display: flex; flex-direction: column; gap: 6rpx; }
.channel-name { font-size: 30rpx; font-weight: 600; color: #0F172A; }
.channel-hint { font-size: 22rpx; color: #94A3B8; }

.channel-body { padding: 24rpx 28rpx; display: flex; flex-direction: column; gap: 20rpx; }

.form-row { display: flex; align-items: center; gap: 16rpx; }
.form-row.col { flex-direction: column; align-items: flex-start; gap: 8rpx; }
.form-label { font-size: 26rpx; color: #64748B; min-width: 140rpx; }
.form-input { flex: 1; font-size: 28rpx; color: #0F172A; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10rpx; padding: 16rpx 20rpx; }
.form-input.short { width: 120rpx; flex: none; }

.level-tags { display: flex; gap: 8rpx; flex-wrap: wrap; }
.level-tag {
  font-size: 22rpx;
  padding: 8rpx 20rpx;
  border-radius: 8rpx;
  background: #F1F5F9;
  color: #64748B;
  border: 1px solid #E2E8F0;
  font-weight: 500;
}
.level-tag.active { background: #0F172A; color: #fff; border-color: #0F172A; }

.form-switch { display: flex; align-items: center; gap: 8rpx; margin-left: auto; }
.switch-label { font-size: 24rpx; color: #64748B; }

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
