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

// 获取舆情列表数据
export const getRiskList = (params) => {
  return request({
    url: '/api/risks', // 对应你后端的路由
    method: 'GET',
    data: params
  });
};

// 获取首页统计数据
export const getDashboardStats = () => {
  return request({
    url: '/api/stats',
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