/**
 * P2 SSE 多事件协议类型（与后端 services/agent_service/sse.py 一一对应）
 *
 * 事件类型：
 *   - text         LLM 流式文本片段（data 是 JSON 编码字符串）
 *   - tool_call    LLM 决定调工具
 *   - tool_progress 流式工具增量 partial
 *   - tool_result  工具完成
 *   - error        工具或主循环异常
 *   - done         当前回复结束
 *
 * 设计来源：AGENT_REDESIGN.md §6
 */

export type SSEEventName =
  | 'text'
  | 'tool_call'
  | 'tool_progress'
  | 'tool_result'
  | 'error'
  | 'done';

export interface SSEToolCall {
  call_id: string;
  tool: string;
  args: Record<string, unknown>;
}

export interface SSEToolProgress {
  call_id: string;
  partial: Record<string, unknown>;
}

export interface SSEToolResult {
  call_id: string;
  success: boolean;
  data: unknown;
  ui: UIEnvelope;
  error: string;
  error_type: string;
}

/** 工具/卡片共用 UI 信封（与后端 ToolResult.to_json() 一致） */
export interface UIEnvelope {
  type: string;
  data: Record<string, unknown>;
  action?: string;
  before?: unknown;
  streamable?: boolean;
  next_action?: string;
}

export interface SSEError {
  call_id?: string;
  message: string;
  error_type: string;
}

/** 协议原文 → 解析后事件 */
export type ParsedSSEEvent =
  | { event: 'text'; data: string }
  | { event: 'tool_call'; data: SSEToolCall }
  | { event: 'tool_progress'; data: SSEToolProgress }
  | { event: 'tool_result'; data: SSEToolResult }
  | { event: 'error'; data: SSEError }
  | { event: 'done'; data: '' };

/** 助手消息内嵌的工具调用单元 */
export interface ToolCallBlock {
  call_id: string;
  tool: string;
  args: Record<string, unknown>;
  result?: SSEToolResult;
  status: 'pending' | 'streaming' | 'success' | 'error';
}

/** 消息中可消费的 UI 卡（来自 tool_result.ui） */
export interface UICard {
  key: string; // 唯一 key（call_id）
  ui: UIEnvelope;
  data: unknown;
  tool: string;
}

/** 流式中的助手消息（多 block 组成） */
export interface AssistantMessage {
  role: 'assistant';
  text: string;
  toolCalls: ToolCallBlock[];
  cards: UICard[];
  done: boolean;
  error?: string;
}
