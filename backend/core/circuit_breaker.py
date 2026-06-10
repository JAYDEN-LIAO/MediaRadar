"""Circuit Breaker 实现 — 防止 LLM 服务雪崩"""
import time
from enum import Enum
from core.metrics import CIRCUIT_BREAKER_STATE

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

# 状态 → Gauge 数值映射（修复 #3.2）
_STATE_TO_GAUGE = {
    CircuitState.CLOSED: 0,
    CircuitState.HALF_OPEN: 1,
    CircuitState.OPEN: 2,
}

class CircuitBreakerOpen(Exception):
    """熔断器开启异常"""
    pass

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time: float = 0
        # 初始化 gauge
        CIRCUIT_BREAKER_STATE.labels(name=self.name).set(_STATE_TO_GAUGE[self._state])

    def call(self, fn, *args, **kwargs):
        """同步调用，受熔断保护"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._set_state(CircuitState.HALF_OPEN)
            else:
                raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN (retry after {self.recovery_timeout}s)")

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _set_state(self, new_state: CircuitState):
        """更新状态并同步到 Prometheus gauge（修复 #3.2）"""
        if new_state != self._state:
            self._state = new_state
            CIRCUIT_BREAKER_STATE.labels(name=self.name).set(_STATE_TO_GAUGE[new_state])

    def _on_success(self):
        self._failures = 0
        if self._state == CircuitState.HALF_OPEN:
            self._set_state(CircuitState.CLOSED)

    def _on_failure(self):
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            self._set_state(CircuitState.OPEN)

    # 显式接口（修复 #3.2 测试需要）
    def record_failure(self):
        """外部测试/手动触发失败（同步设置 _last_failure_time）"""
        self._on_failure()

    def record_success(self):
        """外部测试/手动触发成功"""
        self._on_success()

    @property
    def state(self) -> CircuitState:
        return self._state

    def to_dict(self) -> dict:
        """导出为 dict（用于 /api/circuit/states 端点）"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failures,
            "threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }
