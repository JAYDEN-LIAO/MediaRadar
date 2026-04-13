"""
AgentMemoryManager: 检索/写入时机决策，LLM 摘要生成，context 注入
"""
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from openai import OpenAI
from core.config import settings
from core.logger import get_logger
from .memory_store import AgentMemoryStore

logger = get_logger("agent.memory")

class AgentMemoryManager:
    """记忆管理器"""

    def __init__(self):
        self.store = AgentMemoryStore()
        self.ttl_days = getattr(settings, 'AGENT_MEMORY_TTL_DAYS', 90)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.ANALYST_API_KEY,
                base_url=settings.ANALYST_BASE_URL
            )
        return self._client

    def build_working_memory(self, session_id: str) -> str:
        """
        对话开始时调用：检索长期记忆，构建【用户记忆】段落。
        """
        parts = []

        # 检索高频实体
        entities = self.store.get_frequent_entities(session_id, min_count=2)
        if entities:
            entity_lines = []
            for e in entities:
                sensitivity_tag = f"[敏感度: {e['sensitivity']}]" if e.get('sensitivity') != 'balanced' else ""
                entity_lines.append(
                    f"- {e['entity']}（{e['entity_type']}）{sensitivity_tag}，"
                    f"查询 {e['query_count']} 次"
                    + (f"，摘要: {e['last_summary']}" if e.get('last_summary') else "")
                )
            parts.append("【用户高频关注实体】\n" + "\n".join(entity_lines))

        # 检索事实记忆
        facts = self.store.get_valid_facts(session_id)
        if facts:
            fact_lines = [f"- {f['entity']}: {f['content']}" for f in facts[:5]]
            parts.append("【已确认事实】\n" + "\n".join(fact_lines))

        # 检索行为模式
        patterns = self.store.get_recent_patterns(session_id, days=7)
        if patterns:
            pattern_lines = [f"- {p['pattern_type']}: {p['pattern_value']}" for p in patterns]
            parts.append("【用户偏好】\n" + "\n".join(pattern_lines))

        if not parts:
            return ""

        return "\n\n".join(parts)

    def write_from_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        outcome: str = None
    ):
        """
        对话结束时调用：提取实体、写入 fact_memory、更新 pattern_memory、生成摘要。
        messages: [{"role": "user"/"assistant", "content": "..."}]
        """
        # 1. LLM 生成摘要
        summary = self._summarize_conversation(messages)

        # 2. 提取实体
        entities = self._extract_entities(summary)

        # 3. 写入摘要
        self.store.save_summary(session_id, summary, entities, outcome)

        # 4. 写入实体记忆
        for entity_text, entity_type in entities:
            self.store.upsert_entity(session_id, entity_text, entity_type)

        # 5. 分析并写入行为模式
        self._analyze_and_write_patterns(session_id, messages)

        logger.info(f"💾 [Memory] 已写入对话 {session_id} 的记忆：{len(entities)} 个实体")

    def _summarize_conversation(self, messages: List[Dict[str, str]]) -> str:
        """LLM 生成 50 字对话摘要"""
        if not messages:
            return "用户未提问"

        messages_text = "\n".join([
            f"{'用户' if m['role']=='user' else '助手'}: {m['content'][:100]}"
            for m in messages[-6:]  # 最近 6 条
        ])

        prompt = f"""用50字以内概括以下对话的核心意图和结果：

{messages_text}

直接返回摘要文字，不需要解释。"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"摘要生成失败: {e}")
            return f"对话包含 {len(messages)} 条消息"

    def _extract_entities(self, summary: str) -> List[tuple]:
        """从摘要中提取实体（简单规则 + LLM）"""
        # 简单实体识别（关键词/品牌）
        known_entities = ["华为", "苹果", "小米", "抖音", "微博", "小红书", "知乎", "B站"]
        found = []
        for entity in known_entities:
            if entity in summary:
                found.append((entity, "brand"))

        if found:
            return found

        # 无已知实体，返回空
        return []

    def _analyze_and_write_patterns(self, session_id: str, messages: List[Dict[str, str]]):
        """分析并写入行为模式"""
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return

        # 简单模式识别
        last_msg = user_messages[-1]["content"]
        if len(last_msg) < 20:
            self.store.upsert_pattern(session_id, "answer_length", "short")
        elif len(last_msg) < 100:
            self.store.upsert_pattern(session_id, "answer_length", "medium")
        else:
            self.store.upsert_pattern(session_id, "answer_length", "long")

    def delete_session(self, session_id: str):
        """删除某次对话记忆"""
        self.store.delete_session(session_id)

    def get_stats(self) -> Dict[str, int]:
        """获取记忆统计"""
        return self.store.get_memory_stats()