// src/utils/api.js

// 这里填写你 Python 后端的本地 IP 或域名
// 注意：如果你是用手机预览，不能写 127.0.0.1，要写你电脑的局域网 IP（比如 192.168.x.x）
// 目前我们在电脑模拟器里看，用 127.0.0.1 没问题
const BASE_URL = 'http://127.0.0.1:8000'; 

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