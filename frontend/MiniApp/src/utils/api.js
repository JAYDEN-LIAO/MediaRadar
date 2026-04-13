// src/utils/api.js

// 这里填写你 Python 后端的本地 IP 或域名
// 注意：如果你是用手机预览，不能写 127.0.0.1，要写你电脑的局域网 IP（比如 192.168.x.x）
// 目前我们在电脑模拟器里看，用 127.0.0.1 没问题
const BASE_URL = 'http://127.0.0.1:8008'; 

export const request = (options) => {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...options.header
      },
      success: (res) => {
        // HTTP 状态码 200 表示请求成功
        if (res.statusCode === 200) {
          resolve(res.data);
        } else {
          uni.showToast({ title: '服务器开小差了', icon: 'none' });
          reject(res.data);
        }
      },
      fail: (err) => {
        uni.showToast({ title: '网络连接失败', icon: 'none' });
        console.error('API请求错误:', err);
        reject(err);
      }
    });
  });
};

// ----------------- 具体的接口定义 -----------------

// 获取近7日声量统计（用于首页趋势图）
export const getVolumeStats = (keyword) => {
  return request({
    url: '/api/volume_stats',
    method: 'GET',
    data: { keyword: keyword || '' }
  });
};

// 获取今日AI摘要
export const getTodaySummary = () => {
  return request({
    url: '/api/today_summary',
    method: 'GET'
  });
};

// ----------------- 话题聚合 API（任务6） -----------------

// 获取话题列表
export const getTopicList = (params) => {
  return request({
    url: '/api/topic_list',
    method: 'GET',
    data: params
  });
};

// 获取话题详情（含关联帖子）
export const getTopicDetail = (topicId) => {
  return request({
    url: `/api/topic/${topicId}`,
    method: 'GET'
  });
};

// 标记话题为已处理
export const markTopicProcessed = (topicId) => {
  return request({
    url: `/api/topic/${topicId}/process`,
    method: 'POST'
  });
};

export const streamRequest = (url, data, onChunk, onDone, onError) => {
  // 注意：小程序支持 enableChunked
  const requestTask = uni.request({
    url: BASE_URL + url,
    method: 'POST',
    data: data,
    enableChunked: true, // 开启流式接收
    header: {
      'Content-Type': 'application/json'
    },
    success: (res) => {
      if (res.statusCode !== 200) {
        uni.showToast({ title: 'Agent 开小差了', icon: 'none' });
        if(onError) onError(res);
      } else {
        if(onDone) onDone();
      }
    },
    fail: (err) => {
      console.error('Agent请求失败:', err);
      if(onError) onError(err);
    }
  });

  // 监听数据块到达
  requestTask.onChunkReceived((res) => {
    try {
      // 微信小程序返回的是 ArrayBuffer，需要转成字符串
      const uint8Array = new Uint8Array(res.data);
      // 兼容小程序的 TextDecoder 解析 UTF-8
      let text = '';
      if (typeof TextDecoder !== 'undefined') {
        const decoder = new TextDecoder('utf-8');
        text = decoder.decode(uint8Array);
      } else {
        // 极低版本基础库兼容写法（若报错可忽略，现在几乎都支持 TextDecoder）
        text = decodeURIComponent(escape(String.fromCharCode.apply(null, uint8Array)));
      }
      onChunk(text);
    } catch (e) {
      console.error('流数据解析失败', e);
    }
  });

  return requestTask; // 返回 task 以便外部可以随时 abort (停止生成)
};

// ----------------- 记忆库 API（任务14） -----------------

/**
 * 获取记忆库统计状态
 */
export const getMemory = () => {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}/api/agent/memory`,
      method: 'GET',
      header: {
        'Content-Type': 'application/json'
      },
      success: (res) => {
        if (res.data.success) {
          resolve(res.data.data)
        } else {
          reject(new Error(res.data.error || '获取记忆状态失败'))
        }
      },
      fail: reject
    })
  })
}

/**
 * 获取指定 session 的记忆详情
 * @param {String} sessionId - 会话 ID
 */
export const getSessionMemory = (sessionId) => {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}/api/agent/memory/${sessionId}`,
      method: 'GET',
      header: {
        'Content-Type': 'application/json'
      },
      success: (res) => {
        if (res.data.success) {
          resolve(res.data.data)
        } else {
          reject(new Error(res.data.error || '获取会话记忆失败'))
        }
      },
      fail: reject
    })
  })
}

/**
 * 清除指定 session 的记忆
 * @param {String} sessionId - 会话 ID
 */
export const clearMemory = (sessionId) => {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}/api/agent/memory/${sessionId}`,
      method: 'DELETE',
      header: {
        'Content-Type': 'application/json'
      },
      success: (res) => {
        if (res.data.success) {
          resolve(res.data.message)
        } else {
          reject(new Error(res.data.error || '清除记忆失败'))
        }
      },
      fail: reject
    })
  })
}

// ----------------- 推送配置 API -----------------

/** 获取所有推送通道简洁配置（不含密码） */
export const getPushConfigs = () => {
  return request({
    url: '/api/push/configs',
    method: 'GET'
  });
};

/** 获取单个通道完整配置（含密码） */
export const getPushConfig = (channel) => {
  return request({
    url: `/api/push/config/${channel}`,
    method: 'GET'
  });
};

/** 保存推送通道配置 */
export const savePushConfig = (channel, data) => {
  return request({
    url: `/api/push/config/${channel}`,
    method: 'POST',
    data
  });
};

/** 测试推送通道 */
export const testPushChannel = (channel) => {
  return request({
    url: '/api/push/test',
    method: 'POST',
    data: { channel }
  });
};

// ----------------- 大模型 API 配置 -----------------

/** 获取所有 LLM Agent 配置 */
export const getLlmConfigs = () => {
  return request({
    url: '/api/llm/configs',
    method: 'GET'
  });
};

/** 更新单个 LLM Agent 配置 */
export const updateLlmConfig = (agent, data) => {
  return request({
    url: `/api/llm/config/${agent}`,
    method: 'POST',
    data
  });
};

/** 测试 LLM Agent 连通性 */
export const testLlmConfig = (agent) => {
  return request({
    url: `/api/llm/test/${agent}`,
    method: 'POST'
  });
};