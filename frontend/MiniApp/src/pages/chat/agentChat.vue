<template>
  <view class="chat-container">
    <scroll-view 
      scroll-y 
      class="chat-scroll" 
      :scroll-into-view="scrollToId"
      scroll-with-animation
    >
      <view class="message-list">
        <view class="message-item assistant">
          <view class="avatar">🤖</view>
          <view class="bubble">您好！我是您的专属舆情智能体。我可以帮您总结近期预警，或立即触发全网扫雷。请问有什么可以帮您？</view>
        </view>

        <view 
          v-for="(msg, index) in messages" 
          :key="index" 
          class="message-item" 
          :class="msg.role"
          :id="'msg-' + index"
        >
          <view class="avatar" v-if="msg.role === 'assistant'">🤖</view>
          <view class="bubble">
            <text class="msg-text">{{ msg.content }}</text>
            <view v-if="msg.isGenerating" class="cursor"></view>
          </view>
          <view class="avatar user-avatar" v-if="msg.role === 'user'">👤</view>
        </view>
      </view>
      <view class="bottom-spacer" id="scroll-bottom"></view>
    </scroll-view>

    <view class="input-bar">
      <input 
        class="input-box" 
        v-model="inputText" 
        placeholder="例如: 最近系统里有什么高风险舆情吗？" 
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
import { streamRequest } from '@/utils/api.js' // 请确保路径与你实际项目匹配

export default {
  data() {
    return {
      inputText: '',
      messages: [],
      isGenerating: false,
      scrollToId: '',
      currentTask: null // 用于保存请求Task，便于随时停止
    }
  },
  methods: {
    sendMessage() {
      if (!this.inputText.trim() || this.isGenerating) return;

      const userMsg = this.inputText.trim();
      this.inputText = '';
      
      // 1. 用户消息上屏
      this.messages.push({ role: 'user', content: userMsg });
      this.scrollToBottom();

      // 2. 准备 AI 消息占位符
      this.messages.push({ role: 'assistant', content: '', isGenerating: true });
      this.isGenerating = true;
      this.scrollToBottom();

      // 构造给后端的上下文
      const payloadMessages = this.messages
        .filter(m => !m.isGenerating) // 过滤掉正在生成的占位标记
        .map(m => ({ role: m.role, content: m.content }));

      // 获取当前正在生成的这条消息的索引
      const currentIndex = this.messages.length - 1;

      // 3. 发起流式请求
      this.currentTask = streamRequest(
        '/api/agent/chat',
        { messages: payloadMessages },
        // onChunk: 处理流式数据
        (chunkText) => {
          this.parseSSEChunk(chunkText, currentIndex);
        },
        // onDone
        () => {
          this.messages[currentIndex].isGenerating = false;
          this.isGenerating = false;
          this.scrollToBottom();
        },
        // onError
        (err) => {
          this.messages[currentIndex].content += '\n[网络请求中断或发生错误]';
          this.messages[currentIndex].isGenerating = false;
          this.isGenerating = false;
        }
      );
    },

    // 解析 SSE 数据格式 (data: xxxx\n\n)
    parseSSEChunk(chunkText, index) {
      // chunkText 可能一次性包含多个 "data: xxx\n\n"
      const lines = chunkText.split('\n\n');
      for (let line of lines) {
        if (line.startsWith('data: ')) {
          const dataContent = line.replace('data: ', '');
          if (dataContent.trim() === '[DONE]') {
            this.messages[index].isGenerating = false;
            this.isGenerating = false;
            break;
          }
          // 将文字拼接到当前 AI 气泡中
          this.messages[index].content += dataContent;
          this.scrollToBottom();
        }
      }
    },

    scrollToBottom() {
      this.$nextTick(() => {
        // 滚动到列表最底部
        this.scrollToId = 'scroll-bottom';
      });
    }
  },
  onUnload() {
    // 页面卸载时，如果正在生成，强制中断请求
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
  background-color: #F3F4F6;
}

.chat-scroll {
  flex: 1;
  overflow: hidden;
}

.message-list {
  padding: 30rpx;
}

.message-item {
  display: flex;
  margin-bottom: 40rpx;
  align-items: flex-start;
}

.message-item.user {
  justify-content: flex-end;
}

.avatar {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  background-color: #E5E7EB;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 40rpx;
  margin-right: 20rpx;
}

.user-avatar {
  margin-right: 0;
  margin-left: 20rpx;
  background-color: #10B981;
}

.bubble {
  max-width: 70%;
  padding: 24rpx;
  border-radius: 20rpx;
  font-size: 30rpx;
  line-height: 1.5;
  color: #111827;
  word-break: break-all;
}

.message-item.assistant .bubble {
  background-color: #FFFFFF;
  border-top-left-radius: 4rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.05);
}

.message-item.user .bubble {
  background-color: #10B981;
  color: #FFFFFF;
  border-top-right-radius: 4rpx;
}

.msg-text {
  white-space: pre-wrap; /* 保证换行符能正常显示 */
}

/* 简单的闪烁光标效果 */
.cursor {
  display: inline-block;
  width: 4rpx;
  height: 30rpx;
  background-color: #10B981;
  vertical-align: middle;
  margin-left: 4rpx;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.bottom-spacer {
  height: 40rpx;
}

.input-bar {
  display: flex;
  align-items: center;
  padding: 20rpx 30rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  background-color: #FFFFFF;
  border-top: 1rpx solid #E5E7EB;
}

.input-box {
  flex: 1;
  height: 80rpx;
  background-color: #F3F4F6;
  border-radius: 40rpx;
  padding: 0 30rpx;
  font-size: 28rpx;
}

.send-btn {
  margin-left: 20rpx;
  width: 120rpx;
  height: 80rpx;
  background-color: #10B981;
  color: #fff;
  border-radius: 40rpx;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 28rpx;
  transition: opacity 0.2s;
}

.send-btn.disabled {
  opacity: 0.5;
}
</style>