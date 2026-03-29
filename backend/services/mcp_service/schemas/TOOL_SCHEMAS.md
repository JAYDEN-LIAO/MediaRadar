# MediaRadar MCP Tools JSON Schema 文档

本文档为每个 Tool 提供输入/输出 Schema，可供 AI Agent 或客户端做类型校验。

---

## 1. 爬虫工具

### crawl_platform

```json
{
  "name": "crawl_platform",
  "description": "抓取指定平台的舆情数据。会在后台启动爬虫任务。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "platform": {
        "type": "string",
        "description": "平台标识，支持: wb/xhs/bili/zhihu/dy/ks/tieba",
        "examples": ["wb", "xhs"]
      },
      "keyword": {
        "type": ["string", "null"],
        "description": "搜索关键词，不填则使用系统配置的全局关键词",
        "examples": ["华为"]
      },
      "headless": {
        "type": "boolean",
        "description": "是否无头模式（True=不显示浏览器）",
        "default": false,
        "examples": [false]
      }
    },
    "required": ["platform"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "message": {"type": "string"},
      "task_id": {"type": ["string", "null"]},
      "is_running": {"type": "boolean"},
      "error": {"type": ["string", "null"]}
    }
  }
}
```

### crawl_all_platforms

```json
{
  "name": "crawl_all_platforms",
  "description": "全平台抓取。对所有支持平台同时下发爬虫任务。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keyword": {
        "type": ["string", "null"],
        "description": "搜索关键词，不填则使用系统配置的全局关键词"
      },
      "headless": {
        "type": "boolean",
        "description": "是否无头模式",
        "default": false
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "message": {"type": "string"},
      "platforms": {"type": "array", "items": {"type": "string"}},
      "details": {"type": "array"},
      "error": {"type": ["string", "null"]}
    }
  }
}
```

### get_crawler_status

```json
{
  "name": "get_crawler_status",
  "description": "获取爬虫的当前运行状态（是否在运行、平台、启动时间）。无参数。",
  "inputSchema": {"type": "object", "properties": {}},
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "object",
        "properties": {
          "is_running": {"type": "boolean"},
          "status": {"type": "string"},
          "platform": {"type": ["string", "null"]},
          "crawler_type": {"type": ["string", "null"]},
          "started_at": {"type": ["string", "null"]}
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

---

## 2. Pipeline 工具

### screener_posts

```json
{
  "name": "screener_posts",
  "description": "文本初筛帖子。对一批帖子进行 LLM 驱动的初筛，判断是否与监控关键词相关。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "posts": {
        "type": "array",
        "description": "待筛选的帖子列表，每条包含 post_id/title/content/url/image_urls/platform",
        "items": {
          "type": "object",
          "properties": {
            "post_id": {"type": "string"},
            "title": {"type": "string"},
            "content": {"type": "string"},
            "url": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "platform": {"type": "string"}
          },
          "required": ["post_id", "title", "content"]
        }
      },
      "keywords": {
        "type": "array",
        "description": "监控关键词列表",
        "items": {"type": "string"},
        "examples": [["华为", "苹果"]]
      },
      "keyword_levels": {
        "type": ["object", "null"],
        "description": "关键词对应的敏感度，aggressive/balanced/conservative",
        "examples": [{"华为": "aggressive", "苹果": "balanced"}]
      }
    },
    "required": ["posts", "keywords"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "post": {"type": "object"},
            "matched_keyword": {"type": "string"},
            "vision_text": {"type": "string"}
          }
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

### vision_analyze

```json
{
  "name": "vision_analyze",
  "description": "视觉图片分析。调用 Qwen-VL-Max 对图片进行多模态分析，提取视觉证据。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "image_url": {
        "type": "string",
        "description": "图片 URL 或本地路径",
        "examples": ["https://example.com/image.jpg"]
      },
      "post_text": {
        "type": "string",
        "description": "帖子正文（可选，用于结合图片做分析）",
        "default": ""
      },
      "platform": {
        "type": "string",
        "description": "平台标识",
        "default": "wb",
        "examples": ["wb", "xhs"]
      }
    },
    "required": ["image_url"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "object",
        "properties": {
          "vision_text": {"type": "string"},
          "platform": {"type": "string"},
          "image_url": {"type": "string"}
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

### cluster_posts

```json
{
  "name": "cluster_posts",
  "description": "向量聚类帖子。将一批帖子通过 BGE-M3 embedding + HDBSCAN 聚类，按语义相似度归并为话题簇。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "posts": {
        "type": "array",
        "description": "待聚类的帖子列表",
        "items": {"type": "object"}
      },
      "keyword": {
        "type": "string",
        "description": "监控关键词",
        "examples": ["华为"]
      }
    },
    "required": ["posts", "keyword"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "topic_name": {"type": "string"},
            "post_ids": {"type": "array", "items": {"type": "string"}},
            "keyword": {"type": "string"}
          }
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

### analyze_cluster

```json
{
  "name": "analyze_cluster",
  "description": "LangGraph 全链路分析。对一个话题簇进行 DeepSeek(analyst) → Kimi(reviewer) → Kimi(director) 三节点分析，输出风险等级、核心问题、预警简报。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "posts": {
        "type": "array",
        "description": "该话题簇下的帖子列表",
        "items": {"type": "object"}
      },
      "keyword": {
        "type": "string",
        "description": "监控关键词"
      },
      "sensitivity": {
        "type": "string",
        "description": "分析敏感度：aggressive（激进）/ balanced（平衡）/ conservative（保守）",
        "default": "balanced",
        "examples": ["balanced"]
      }
    },
    "required": ["posts", "keyword"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "object",
        "properties": {
          "status": {"type": "string", "enum": ["safe", "alert"]},
          "risk_level": {"type": "integer"},
          "core_issue": {"type": "string"},
          "report": {"type": "string"},
          "reason": {"type": "string"}
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

### analyze_cluster_stream

```json
{
  "name": "analyze_cluster_stream",
  "description": "LangGraph 全链路分析（SSE流式版本）。与 analyze_cluster 相同，但通过 SSE 流式输出每个节点的进度。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "posts": {"type": "array", "items": {"type": "object"}},
      "keyword": {"type": "string"},
      "sensitivity": {"type": "string", "default": "balanced"}
    },
    "required": ["posts", "keyword"]
  },
  "outputSchema": "SSE stream of events",
  "eventTypes": [
    {"event": "analysis_progress", "data": {"node": "analyst|reviewer|director", "status": "started|completed", "risk_level": "integer"}},
    {"event": "final_result", "data": {"result": "object", "topic_name": "string"}},
    {"event": "completed", "data": {"total_results": "integer"}},
    {"event": "error", "data": {"error": "string", "stage": "string"}}
  ]
}
```

### run_full_pipeline

```json
{
  "name": "run_full_pipeline",
  "description": "端到端完整分析管线。输入一个关键词，自动执行：抓取 → 初筛 → 聚类 → 分析 → 预警。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keyword": {
        "type": "string",
        "description": "监控关键词"
      },
      "platform": {
        "type": ["string", "null"],
        "description": "指定平台，不填则使用系统配置的全平台"
      },
      "sensitivity": {
        "type": "string",
        "description": "分析敏感度",
        "default": "balanced"
      }
    },
    "required": ["keyword"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "message": {"type": "string"},
      "data": {
        "type": "object",
        "properties": {
          "keyword": {"type": "string"},
          "platform": {"type": ["string", "null"]},
          "sensitivity": {"type": "string"},
          "crawl_status": {"type": "object"}
        }
      }
    }
  }
}
```

---

## 3. 预警与状态工具

### get_radar_status

```json
{
  "name": "get_radar_status",
  "description": "获取舆情雷达系统的当前运行状态。",
  "inputSchema": {"type": "object", "properties": {}},
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "object",
        "properties": {
          "radar": {
            "type": "object",
            "properties": {
              "is_running": {"type": "boolean"},
              "status_text": {"type": "string"},
              "last_run_time": {"type": "string"},
              "last_new_count": {"type": "integer"}
            }
          },
          "crawler": {"type": "object"}
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

### get_recent_alerts

```json
{
  "name": "get_recent_alerts",
  "description": "查询数据库中高危舆情预警历史记录。返回风险等级 >= 指定阈值的所有预警。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "limit": {
        "type": "integer",
        "description": "返回记录条数，默认5条",
        "default": 5,
        "minimum": 1,
        "maximum": 100
      },
      "min_level": {
        "type": "integer",
        "description": "最低风险等级阈值（1-5），默认3",
        "default": 3,
        "minimum": 1,
        "maximum": 5
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "title": {"type": "string"},
            "platform": {"type": "string"},
            "keyword": {"type": "string"},
            "risk_level": {"type": "integer"},
            "core_issue": {"type": "string"},
            "report": {"type": "string"},
            "publish_time": {"type": "string"},
            "emoji": {"type": "string"},
            "risk_text": {"type": "string"}
          }
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

### send_alert

```json
{
  "name": "send_alert",
  "description": "手动发送舆情预警。通过 Server酱/钉钉等渠道推送预警通知。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keyword": {"type": "string", "description": "监控关键词"},
      "platform": {"type": "string", "description": "平台标识"},
      "risk_level": {"type": "integer", "description": "风险等级 1-5", "minimum": 1, "maximum": 5},
      "core_issue": {"type": "string", "description": "核心问题概括"},
      "report": {"type": "string", "description": "预警简报内容"},
      "urls": {"type": "array", "items": {"type": "string"}, "description": "相关链接列表"}
    },
    "required": ["keyword", "platform", "risk_level", "core_issue", "report"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "message": {"type": "string"},
      "error": {"type": ["string", "null"]}
    }
  }
}
```

---

## 4. 配置管理工具

### get_keywords

```json
{
  "name": "get_keywords",
  "description": "获取当前系统配置的监控关键词列表、平台、敏感度等信息。",
  "inputSchema": {"type": "object", "properties": {}},
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "data": {
        "type": "object",
        "properties": {
          "keywords": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {"type": "string"},
                "level": {"type": "string"},
                "level_text": {"type": "string"}
              }
            }
          },
          "platforms": {"type": "array", "items": {"type": "string"}},
          "platforms_raw": {"type": "array", "items": {"type": "string"}},
          "alert_negative": {"type": "boolean"}
        }
      },
      "message": {"type": "string"}
    }
  }
}
```

### update_keywords

```json
{
  "name": "update_keywords",
  "description": "更新舆情雷达的监控关键词配置。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keywords": {
        "type": "array",
        "description": "新的关键词列表（会替换现有配置）",
        "items": {"type": "string"},
        "examples": [["华为", "苹果", "小米"]]
      },
      "keyword_levels": {
        "type": ["object", "null"],
        "description": "关键词对应的敏感度映射，不提供的关键词默认 balanced",
        "examples": [{"华为": "aggressive", "苹果": "balanced"}]
      }
    },
    "required": ["keywords"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": {"type": "boolean"},
      "message": {"type": "string"},
      "data": {
        "type": "object",
        "properties": {
          "keywords": {"type": "array", "items": {"type": "string"}},
          "keyword_levels": {"type": "object"}
        }
      },
      "error": {"type": ["string", "null"]}
    }
  }
}
```

---

## Resources Schema

### radar://status

```
类型: object
内容: { radar: {...}, crawler: {...}, display: {...} }
```

### radar://keywords

```
类型: object
内容: { keywords: [...], total_keywords: int, platforms: [...], alert_negative: bool }
```

### radar://platforms

```
类型: object
内容: { platforms: [{id, name, icon, description}, ...], total: int }
```

### radar://alerts

```
类型: object
内容: { items: [...], total: int, query: {limit, min_level} }
```

### radar://yq-list

```
类型: object
内容: { items: [...], total: int, page: int, page_size: int, total_pages: int }
```
