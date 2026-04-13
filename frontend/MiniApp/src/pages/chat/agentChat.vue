<template>
  <view class="chat-container">
    <view class="chat-header">
      <view class="header-left">
        <view class="ai-avatar">
          <view class="avatar-lines"></view>
        </view>
        <view class="header-info">
          <text class="header-title">舆情智能体</text>
          <text class="header-status">在线</text>
        </view>
      </view>
    </view>

    <scroll-view
      scroll-y
      class="chat-scroll"
      :scroll-into-view="scrollToId"
      scroll-with-animation
    >
      <view class="message-list">
        <view class="message-item assistant">
          <view class="avatar-wrapper">
            <view class="ai-avatar-small">
              <view class="avatar-lines"></view>
            </view>
          </view>
          <view class="bubble assistant-bubble">
            <text class="msg-text">您好，我是舆情智能体。我可以帮您总结近期预警，或立即触发全网扫描。请问有什么可以帮您？</text>
          </view>
        </view>

        <view
          v-for="(msg, index) in messages"
          :key="index"
          class="message-item"
          :class="msg.role"
          :id="'msg-' + index"
        >
          <view class="avatar-wrapper" v-if="msg.role === 'assistant'">
            <view class="ai-avatar-small">
              <view class="avatar-lines"></view>
            </view>
          </view>
          <view class="bubble" :class="msg.role === 'user' ? 'user-bubble' : 'assistant-bubble'">
            <text class="msg-text">{{ msg.content }}</text>
            <view v-if="msg.isGenerating" class="cursor"></view>
          </view>
          <view class="user-avatar-wrapper" v-if="msg.role === 'user'">
            <view class="user-avatar-small">
              <text class="user-avatar-text">ME</text>
            </view>
          </view>
        </view>
      </view>
      <view class="bottom-spacer" id="scroll-bottom"></view>
    </scroll-view>

    <view v-if="memoryLoaded" class="memory-hint">
      <text class="memory-hint-text">🧠 记忆已加载</text>
    </view>

    <view class="input-bar">
      <input
        class="input-box"
        v-model="inputText"
        placeholder="输入您的问题..."
        :adjust-position="true"
        @confirm="sendMessage"
        confirm-type="send"
        :disabled="isGenerating"
      />
      <view
        class="send-btn"
        :class="{ disabled: !inputText.trim() || isGenerating }"
        @click="sendMessage"
      >
        发送
      </view>
    </view>
  </view>
</template>

<script>
import { streamRequest, getMemory } from '@/utils/api.js'

export default {
  data() {
    return {
      sessionId: '',
      memoryLoaded: false,
      inputText: '',
      messages: [],
      isGenerating: false,
      scrollToId: '',
      currentTask: null
    }
  },
  onLoad() {
      // 生成或恢复 session_id
      const savedSessionId = uni.getStorageSync('agentSessionId')
      if (savedSessionId) {
        this.sessionId = savedSessionId
        this.checkMemoryLoaded()
      } else {
        this.sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
        uni.setStorageSync('agentSessionId', this.sessionId)
      }
    },
  methods: {
    async checkMemoryLoaded() {
      try {
        const stats = await getMemory()
        const entityCount = stats.entity_memory_count || 0
        if (entityCount > 0) {
          this.memoryLoaded = true
          uni.showToast({
            title: `记忆已加载（${entityCount} 个关注实体）`,
            icon: 'none',
            duration: 2000
          })
        }
      } catch (e) {
        console.warn('记忆查询失败:', e)
      }
    },

    sendMessage() {
      if (!this.inputText.trim() || this.isGenerating) return;

      const userMsg = this.inputText.trim();
      this.inputText = '';

      this.messages.push({ role: 'user', content: userMsg });
      this.scrollToBottom();

      this.messages.push({ role: 'assistant', content: '', isGenerating: true });
      this.isGenerating = true;
      this.scrollToBottom();

      const payloadMessages = this.messages
        .filter(m => !m.isGenerating)
        .map(m => ({ role: m.role, content: m.content }));

      const currentIndex = this.messages.length - 1;

      this.currentTask = streamRequest(
        '/api/agent/chat',
        { messages: payloadMessages, session_id: this.sessionId },
        (chunkText) => {
          this.parseSSEChunk(chunkText, currentIndex);
        },
        () => {
          this.messages[currentIndex].isGenerating = false;
          this.isGenerating = false;
          this.scrollToBottom();
        },
        (err) => {
          this.messages[currentIndex].content += '\n[网络请求中断或发生错误]';
          this.messages[currentIndex].isGenerating = false;
          this.isGenerating = false;
        }
      );
    },

    parseSSEChunk(chunkText, index) {
      const lines = chunkText.split('\n\n');
      for (let line of lines) {
        if (line.startsWith('data: ')) {
          const dataContent = line.replace('data: ', '');
          if (dataContent.trim() === '[DONE]') {
            this.messages[index].isGenerating = false;
            this.isGenerating = false;
            break;
          }
          this.messages[index].content += dataContent;
          this.scrollToBottom();
        }
      }
    },

    scrollToBottom() {
      this.$nextTick(() => {
        this.scrollToId = 'scroll-bottom';
      });
    }
  },
  onUnload() {
    if (this.currentTask && this.isGenerating) {
      this.currentTask.abort();
    }
  }
}
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #F8FAFC;
}

/* Header */
.chat-header {
  height: 100rpx;
  background-color: #FFFFFF;
  display: flex;
  align-items: center;
  padding: 0 32rpx;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
}

.ai-avatar {
  width: 64rpx;
  height: 64rpx;
  border-radius: 16rpx;
  background-color: #0F172A;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-lines {
  width: 28rpx;
  height: 20rpx;
  background: repeating-linear-gradient(
    0deg,
    #FFFFFF 0rpx,
    #FFFFFF 4rpx,
    transparent 4rpx,
    transparent 8rpx
  );
}

.header-info {
  margin-left: 16rpx;
  display: flex;
  flex-direction: column;
}

.header-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #0F172A;
}

.header-status {
  font-size: 22rpx;
  color: #059669;
  margin-top: 2rpx;
}

/* Scroll Area */
.chat-scroll {
  flex: 1;
  overflow: hidden;
}

.message-list {
  padding: 32rpx 24rpx;
}

.message-item {
  display: flex;
  margin-bottom: 32rpx;
  align-items: flex-start;
}

.message-item.user {
  justify-content: flex-end;
}

.avatar-wrapper {
  margin-right: 16rpx;
}

.user-avatar-wrapper {
  margin-left: 16rpx;
}

.ai-avatar-small {
  width: 56rpx;
  height: 56rpx;
  border-radius: 14rpx;
  background-color: #0F172A;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-avatar-small .avatar-lines {
  width: 24rpx;
  height: 16rpx;
  background: repeating-linear-gradient(
    0deg,
    #FFFFFF 0rpx,
    #FFFFFF 3rpx,
    transparent 3rpx,
    transparent 6rpx
  );
}

.user-avatar-small {
  width: 56rpx;
  height: 56rpx;
  border-radius: 14rpx;
  background-color: #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-avatar-text {
  font-size: 22rpx;
  font-weight: 600;
  color: #64748B;
  letter-spacing: 1rpx;
}

.bubble {
  max-width: 75%;
  padding: 20rpx 24rpx;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 1.6;
  word-break: break-all;
}

.assistant-bubble {
  background-color: #FFFFFF;
  border-top-left-radius: 6rpx;
  color: #334155;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
}

.user-bubble {
  background-color: #0F172A;
  border-top-right-radius: 6rpx;
  color: #FFFFFF;
}

.msg-text {
  white-space: pre-wrap;
}

.cursor {
  display: inline-block;
  width: 3rpx;
  height: 28rpx;
  background-color: #0891B2;
  vertical-align: middle;
  margin-left: 4rpx;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.bottom-spacer {
  height: 32rpx;
}

/* Memory Hint */
.memory-hint {
  display: flex;
  justify-content: center;
  padding: 6rpx 0;
  background-color: #F8FAFC;
}

.memory-hint-text {
  font-size: 24rpx;
  color: #666;
  background: #f5f5f5;
  padding: 4rpx 16rpx;
  border-radius: 12rpx;
}

/* Input Bar */
.input-bar {
  display: flex;
  align-items: center;
  padding: 20rpx 24rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  background-color: #FFFFFF;
  border-top: 1rpx solid #E2E8F0;
}

.input-box {
  flex: 1;
  height: 80rpx;
  background-color: #F8FAFC;
  border: 1rpx solid #E2E8F0;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 30rpx;
  color: #0F172A;
}

.input-box::placeholder {
  color: #94A3B8;
}

.send-btn {
  margin-left: 16rpx;
  width: 120rpx;
  height: 80rpx;
  background-color: #0F172A;
  color: #fff;
  border-radius: 12rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 30rpx;
  font-weight: 500;
  transition: background-color 0.15s ease;
}

.send-btn.disabled {
  background-color: #94A3B8;
}
</style>
