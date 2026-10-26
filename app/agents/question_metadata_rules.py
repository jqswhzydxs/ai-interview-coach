"""Deterministic, framework-neutral semantic checkpoints; no model/client access."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Topic:
    key: str
    label: str
    pattern: str
    checkpoints: tuple[str, str, str]
    followups: tuple[str, str]


TOPICS = (
    Topic("dependency_fastapi", "FastAPI dependency lifetimes", r"fastapi.{0,70}dependenc|dependenc.{0,70}fastapi|(?-i:\bDepends\s*\()", (
        "Explain Depends, callable parameters and sub-dependencies for the resource actually requested.",
        "Distinguish request-scoped reuse from resource cleanup; explain how a yield dependency releases the resource on failure.",
        "Use a dependency override in an isolated test and restore it afterward; verify acquisition and teardown rather than only the response."), (
        "What changes between an ordinary callable dependency and one that yields a resource?",
        "How would you verify the dependency is cleaned up after an exception and that the override does not leak to another test?")),
    Topic("propagation", "transaction propagation and invocation boundaries", r"transaction.{0,60}propag|propag.{0,60}transaction|requires_new|@transactional|事务传播|事务注解|对象内部调用", (
        "Distinguish joining an existing transaction from starting an independent boundary and explain the requested propagation policy.",
        "Relate the actual invocation path and interception mechanism to whether the declared policy takes effect; internal calls do not automatically cross an interceptor.",
        "Test an inner failure, rollback-only state and an outer rollback; distinguish the observed physical commits from logical method scopes."), (
        "What changes when the call is internal to one object rather than passing through the configured transaction interceptor?",
        "Can the inner work remain committed after the outer work rolls back under the policy you selected?")),
    Topic("index_types", "index access method versus indexed subset", r"b.?tree|hash.{0,8}index|partial.{0,8}index|部分索引|索引类型", (
        "Separate an index access method from a predicate restricting indexed rows; these are not mutually exclusive categories.",
        "Relate equality/range operations, filter predicates and data distribution to the proposed index rather than choosing by its name.",
        "Use a representative execution plan and write-cost comparison, including a case where the filter cannot use the proposed subset."), (
        "Could the proposed access method also index only a subset of rows?",
        "What query predicate must hold before a subset index is applicable?")),
    Topic("sessions", "database session ownership", r"sqlalchemy|(?:database|db|orm).{0,12}session|session.{0,15}(?:lifecycle|boundar|leak|reuse|management)|数据库会话|会话生命周期", (
        "Identify who creates, owns and closes each session; do not share mutable sessions across unrelated requests.",
        "Place commit and rollback at an explicit unit-of-work boundary, including exception and cancellation paths.",
        "Demonstrate cleanup and isolation with an exceptional request, not only a successful return."), (
        "Who owns rollback if a later operation fails after an earlier write?",
        "Which test would detect a session reused by two concurrent requests?")),
    Topic("loading", "relationship loading and I/O boundaries", r"lazy.?load|relationship.{0,10}load|eager.?load|懒加载|关系加载", (
        "Identify which attribute access can trigger additional I/O and whether its session is still usable.",
        "Compare explicit loading with implicit access, considering query count and asynchronous execution boundaries.",
        "Test access after the session closes and account for unexpectedly repeated queries."), (
        "Where could an apparently local attribute read issue a database query?",
        "How would you measure query count and test access outside the session scope?")),
    Topic("dependency", "dependency construction and cleanup", r"dependency|dependencies|\bdepends\b|依赖注入", (
        "Explain construction, injection and lifetime of the specific shared resource in the question.",
        "Separate resource acquisition, use and teardown, including exceptions during use.",
        "Show a test substitution that preserves the resource contract without invoking the real dependency."), (
        "What happens to teardown when the consumer raises an exception?",
        "How would you replace this dependency in a test and restore the original afterward?")),
    Topic("isolation", "transaction isolation and concurrent observations", r"isolation.level|read.committed|repeatable.read|serializable|dirty.read|phantom|事务隔离|隔离级别|读写异常", (
        "State the concurrent operations and the anomalous observation being prevented.",
        "Compare visibility and conflict behavior of the isolation choices under that workload.",
        "Use a reproducible interleaving to check correctness and retry behavior instead of assuming a level solves every race."), (
        "Which two-transaction interleaving would distinguish the proposed isolation choices?",
        "What conflict must the application still detect or retry?")),
    Topic("transactions", "atomicity and transaction boundaries", r"transaction|rollback|\bcommit|atomic|事务|原子|回滚|提交", (
        "Identify the operations inside one atomic boundary and which side effects lie outside it.",
        "Explain failure between steps, rollback ownership and recovery after a partially completed operation.",
        "Test concurrent updates and interruption around commit; do not claim independent resources commit atomically by default."), (
        "What remains observable if failure occurs immediately after commit?",
        "Which operation cannot be rolled back with the database transaction, and how is it recovered?")),
    Topic("queries", "query diagnosis and index trade-offs", r"\bquer(?:y|ies)\b|\bsql\b|index(?:es|ing)?\b|database.{0,15}perform|查询|索引|执行计划", (
        "Inspect the actual query, parameter distribution, execution plan and rows examined before choosing a change.",
        "Relate an index or query rewrite to selectivity, join/filter order and write or storage cost.",
        "Compare representative before-and-after behavior and verify result correctness."), (
        "Which execution-plan observation supports your bottleneck hypothesis?",
        "What workload or parameter distribution could make the proposed index ineffective?")),
    Topic("cache", "cache freshness and failure behavior", r"cache|caching|stale|缓存|失效通知", (
        "Identify the source of truth, read/write order and the freshness guarantee actually required.",
        "Analyze stale reads, concurrent fills and failure between persistence and invalidation.",
        "Verify recovery and origin load when the cache is unavailable; avoid claiming cross-resource atomicity."), (
        "What happens if persistence succeeds but invalidation fails?",
        "How would you limit origin load while checking that stale data eventually converges?")),
    Topic("locking", "coordination of concurrent updates", r"distributed.lock|pessimistic|optimistic|locking|version.check|concurrent.{0,12}update|分布式锁|悲观|乐观|并发更新", (
        "Define the invariant, protected record and ownership of the coordination mechanism.",
        "Compare conflict detection or serialization under failure; include stale owners when leases are used.",
        "Construct a concurrent test that can falsify the claimed protection rather than relying on timing luck."), (
        "How is a stale or losing writer prevented from applying an invalid update?",
        "What interleaving would demonstrate that the invariant is still protected after a failure?")),
    Topic("async", "asynchronous execution boundaries", r"async|synchronous|event.loop|blocking|thread.?pool|异步|同步|阻塞", (
        "Locate where work waits, blocks or consumes compute and identify its execution owner.",
        "Explain a compatible execution boundary without assuming an asynchronous function makes blocking work nonblocking.",
        "Check cancellation, bounded concurrency and cleanup when the caller no longer needs the result."), (
        "Which operation still blocks even when called from an asynchronous function?",
        "Who cancels or cleans up outstanding work when the request ends?")),
    Topic("concurrency", "shared-state and worker lifetime safety", r"goroutine|\bchannel|data.race|concurren|fan.out|shared.state|并发|竞态|协程", (
        "Identify shared state, ownership and the possible interleavings, rather than equating concurrency with parallel speedup.",
        "Choose synchronization or ownership transfer for the stated invariant and bound the lifetime of background work.",
        "Exercise conflicting accesses and cancellation; account for leaked workers and blocked senders or receivers."), (
        "What interleaving would break the proposed shared-state invariant?",
        "How do all workers terminate if one participant fails or the parent is cancelled?")),
    Topic("messages", "message delivery and acknowledgement boundaries", r"message|queue|consumer|acknowledg|delivery.lease|消息|队列|消费|投递", (
        "Separate delivery, processing, durable side effects and acknowledgement in the stated message flow.",
        "Analyze loss, redelivery and interruption between a side effect and acknowledgement.",
        "Check recovery, backpressure and ownership; do not infer a broker or an exactly-once guarantee."), (
        "What occurs if the worker crashes after persisting a side effect but before acknowledgement?",
        "How would you verify recovery from a lost lease or an overwhelmed consumer?")),
    Topic("idempotency", "idempotency and duplicate side effects", r"idempoten|duplicate|oversell|double.spend|幂等|重复扣|重复副作用|去重", (
        "Define the business operation and a stable key for distinguishing a repeat from a different request.",
        "Place duplicate detection and durable state changes inside a defensible atomic boundary.",
        "Check concurrent repeats, expired records and interruption after an external side effect."), (
        "What happens when the same key arrives concurrently before either request commits?",
        "How is a retry distinguished from a new operation after a previous response was lost?")),
    Topic("retry", "retry eligibility and bounded recovery", r"retr(?:y|ies)|backoff|重试", (
        "Distinguish transient, permanent and ambiguous outcomes before deciding whether retry is safe.",
        "Bound the retry budget and delay while preserving cancellation and side-effect safety.",
        "Define the terminal failure and demonstrate that repeated attempts do not amplify load or duplicate effects."), (
        "Which failure must be rejected without another attempt, and why?",
        "What evidence shows that a lost response did not leave an already-completed side effect?")),
    Topic("testing", "test boundaries and isolated state", r"\btest|pytest|fixture|regression|coverage|测试|验收检查|隔离.*用例", (
        "Choose the smallest test boundary that observes the promised behavior and separates local fakes from integration checks.",
        "Control fixture ownership, mutable state, setup and cleanup, including failures during the test.",
        "Include normal, exceptional and concurrent cases where relevant; explain what a passing test does not establish."), (
        "Which state could leak into another test, and how is cleanup verified after failure?",
        "What assertion distinguishes the intended side effect from merely receiving a successful response?")),
    Topic("api", "request contracts and API boundaries", r"\bapi\b|\bhttp|\brest|endpoint|handler|middleware|router|接口|路由|请求参数", (
        "Specify the request/response contract, validation and the owner of business decisions.",
        "Separate routing, application work and persistence, preserving relevant error and cancellation boundaries.",
        "Check invalid input and partial failures without exposing internal data or promising unverified response times."), (
        "Which invalid request must be rejected before any durable side effect?",
        "What observable contract is preserved when an internal dependency fails?")),
    Topic("errors", "failure classification and safe error handling", r"exception|error.handl|validation|outage|unavailable|degrad|错误处理|校验|不可用|降级|失败应", (
        "Separate invalid input or policy rejection from internal and dependency failures.",
        "Assign cleanup and error propagation to explicit owners, preserving the original failure category.",
        "Verify safe external errors and actionable internal signals without leaking secrets or claiming recovery that was not observed."), (
        "Which failure information is safe for the caller and which stays in sanitized diagnostics?",
        "How would a test establish that cleanup still runs when error handling itself is exercised?")),
    Topic("diagnosis", "evidence-based diagnosis", r"debug|diagnos|root.cause|incident|bottleneck|latency|slow|排查|根因|故障|变慢|诊断", (
        "State the symptom, affected boundary and a reproducible or observable trigger.",
        "Compare hypotheses using measurements, logs or a minimal experiment instead of treating correlation as a cause.",
        "Verify the fix and regression prevention with a check tied to the original symptom."), (
        "What observation would disprove your leading hypothesis?",
        "Which check establishes that the root cause is fixed rather than temporarily hidden?")),
    Topic("architecture", "separation of responsibilities", r"architect|structure|layer|modular|maintainab|separat|refactor|架构|分层|模块|职责", (
        "Identify the actual responsibilities, interfaces and direction of dependencies.",
        "Explain a boundary that limits coupling without adding unsupported infrastructure.",
        "Demonstrate how a change or a test can isolate one concern and preserve the external contract."), (
        "Which dependency would make the proposed boundary difficult to test or replace?",
        "What change scenario would demonstrate that the separation improves maintainability?")),
    Topic("ownership", "memory and resource ownership", r"borrow|memory.safety|resource.ownership|outlive|resource.cleanup|内存安全|借用|资源释放", (
        "Identify the resource owner and the lifetime during which references or work remain valid.",
        "Explain transfer, borrowing or cleanup at the boundary stated in the question.",
        "Check interruption and early return without assuming resources outlive their owner."), (
        "Which value or resource could outlive its owner in this example?",
        "What test or static check would expose an invalid lifetime or a missed cleanup path?")),
    Topic("privacy", "credential handling and safe diagnostics", r"credential|secret|sensitive|redact|秘密|凭证|密钥|泄漏", (
        "Identify where a sensitive value enters, is used and must not be exposed; do not print or copy the value.",
        "Fail safely for missing configuration and redact diagnostic or external errors without hiding the failure category.",
        "Use synthetic markers to test that request failures, logging and configuration errors never expose the sensitive value."), (
        "Which error or diagnostic path could accidentally reflect a credential value?",
        "How would a local test prove that missing-secret handling and redaction are both exercised?")),
    Topic("security", "authentication and authorization boundaries", r"authenticat|authoriz|permission|鉴权|权限", (
        "Distinguish identity, permission and resource ownership for the specific operation.",
        "Enforce the boundary before sensitive work and avoid reflecting credentials into logs or errors.",
        "Test denied access, missing credentials and cross-user access without using real secrets."), (
        "Which negative test demonstrates that a different user cannot access the same protected resource?",
        "How would you verify that rejection and diagnostics reveal no credential value?")),
    Topic("collaboration", "collaboration and responsibility", r"collaborat|team|disagreement|feedback|review|stakeholder|协作|团队|分歧|反馈|评审", (
        "Identify the participants, decision boundary and your own contribution without taking credit for others.",
        "Explain how differing constraints or feedback changed the proposed action.",
        "Use a concrete communication or acceptance check to establish shared understanding."), (
        "What evidence changed the decision, and who remained responsible for the result?",
        "How did you establish that the other participants agreed on the acceptance criteria?")),
    Topic("tradeoff", "explicit trade-offs and constraints", r"trade.?off|balance|prioriti|speed.and|取舍|权衡|优先|交付时间", (
        "State the alternatives and the constraint that makes choosing necessary.",
        "Compare consequences using the same workload, correctness condition or delivery commitment.",
        "Identify a decision reversal condition and a check for the chosen compromise."), (
        "Which observation would make you choose the rejected alternative instead?",
        "How would you verify that the compromise did not break the protected requirement?")),
)


def topics_for(text: str) -> list[Topic]:
    ranked = []
    for order, topic in enumerate(TOPICS):
        hits = list(re.finditer(topic.pattern, text, flags=re.I))
        if not hits:
            continue
        # A prohibited mechanism is a constraint, not a recommended solution topic.
        if topic.key == "locking" and re.search(
            r"(?:without|not\s+us\w*|不使用|不用|禁止).{0,28}(?:lock|锁)", text, re.I
        ):
            continue
        specificity = 3 if topic.key in {"dependency_fastapi", "propagation", "index_types", "loading", "isolation", "privacy", "security", "idempotency"} else 1
        ranked.append((len(hits) * specificity, -order, topic))
    return [item[2] for item in sorted(ranked, key=lambda x: (x[0], x[1]), reverse=True)[:3]]
