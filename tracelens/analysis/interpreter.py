"""Evidence interpreter: adds severity, explanation, and suggestions to raw evidence data."""

from __future__ import annotations

import re

from tracelens.types import EvidenceItem


def interpret_evidence(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    """Enrich each evidence item with interpretation — severity, explanation, suggestion."""
    return [_interpret_one(e) for e in evidence]


def _interpret_one(e: EvidenceItem) -> EvidenceItem:
    fn = _INTERPRETERS.get(e.title)
    if fn:
        return fn(e)
    return e


def _interpret_thread_state(e: EvidenceItem) -> EvidenceItem:
    # Parse "Running=XXms, S=XXms, R=XXms"
    states = dict(re.findall(r"(\w+)=(\d+)ms", e.summary))
    total = sum(int(v) for v in states.values()) or 1
    running = int(states.get("Running", 0))
    sleeping = int(states.get("S", 0))
    runnable = int(states.get("R", 0))

    parts = [e.summary]
    if sleeping / total > 0.5:
        parts.append(f"⚠️ 主线程超过 {sleeping*100//total}% 时间在 Sleep 状态，说明频繁被阻塞等待（锁、Binder、I/O）")
    if runnable / total > 0.1:
        parts.append(f"⚠️ {runnable*100//total}% 时间在 Runnable 状态等待调度，说明 CPU 资源竞争严重")
    if running / total > 0.8:
        parts.append("主线程大部分时间在 Running，卡顿可能来自计算密集型操作而非阻塞")

    return EvidenceItem(title=e.title, summary="\n".join(parts))


def _interpret_long_slices(e: EvidenceItem) -> EvidenceItem:
    # Parse "name=XXms on thread"
    slices = re.findall(r"([\w#.]+)=(\d+)ms on (\S+)", e.summary)
    if not slices:
        return e

    parts = [e.summary]
    for name, dur_str, thread in slices[:5]:
        dur = int(dur_str)
        lower_name = name.lower()
        if "inflate" in lower_name:
            parts.append(f"→ {name}({dur}ms): 布局加载耗时，建议 ViewStub 延迟加载或异步预加载")
        elif "loadxmlresource" in lower_name or "resourcesimpl" in lower_name:
            parts.append(f"→ {name}({dur}ms): 资源文件解析耗时，考虑资源预加载或简化 XML 复杂度")
        elif "handleconfigurationchanged" in lower_name:
            parts.append(f"→ {name}({dur}ms): 配置变更（如横竖屏切换）触发重建，考虑减少重建范围或缓存状态")
        elif "handlelaunchactivity" in lower_name or "handleresumeactivity" in lower_name:
            parts.append(f"→ {name}({dur}ms): Activity 生命周期耗时，检查 onCreate/onResume 中的重操作")
        elif "handledestroyactivity" in lower_name:
            parts.append(f"→ {name}({dur}ms): Activity 销毁耗时，检查 onDestroy 中的资源释放逻辑")
        elif "bindapplication" in lower_name:
            parts.append(f"→ {name}({dur}ms): 应用绑定耗时（冷启动），检查 Application.onCreate 和 ContentProvider")
        elif "measure" in lower_name or "layout" in lower_name:
            parts.append(f"→ {name}({dur}ms): 布局测量/排列耗时，检查嵌套层级或复杂约束")
        elif "doframe" in lower_name or "performtraversals" in lower_name:
            parts.append(f"→ {name}({dur}ms): 单帧处理超预算，需要拆分帧内耗时操作")
        elif "binder" in lower_name:
            parts.append(f"→ {name}({dur}ms): 跨进程调用耗时，考虑异步化或减少调用频率")
        elif "gc" in lower_name or name.startswith("young") or name.startswith("concurrent"):
            parts.append(f"→ {name}({dur}ms): GC 暂停，检查内存分配热点，减少临时对象创建")
        elif "dequeueBuffer" in name:
            parts.append(f"→ {name}({dur}ms): 等待 SurfaceFlinger 释放 buffer，可能是合成端瓶颈")
        elif "eglSwapBuffers" in name:
            parts.append(f"→ {name}({dur}ms): GPU 提交耗时，检查渲染复杂度")
        elif "computeFrame" in name or "compute" in lower_name:
            parts.append(f"→ {name}({dur}ms): 计算密集操作，考虑拆分到后台线程或分帧处理")
        elif dur > 50:
            parts.append(f"→ {name}({dur}ms): 严重耗时，需要排查具体逻辑")
        elif dur > 16:
            parts.append(f"→ {name}({dur}ms): 超过单帧预算")

    return EvidenceItem(title=e.title, summary="\n".join(parts))


def _interpret_scheduling_delay(e: EvidenceItem) -> EvidenceItem:
    # Parse "thread=XXms"
    delays = re.findall(r"(\S+)=(\d+)ms", e.summary)
    parts = [e.summary]
    for thread, ms_str in delays[:3]:
        ms = int(ms_str)
        if ms > 100:
            parts.append(f"⚠️ {thread} 调度延迟 {ms}ms 严重偏高，CPU 可能被后台任务或其他进程抢占")
        elif ms > 30:
            parts.append(f"⚠️ {thread} 调度延迟 {ms}ms 偏高，检查是否有 CPU 密集型后台线程")

    return EvidenceItem(title=e.title, summary="\n".join(parts))


def _interpret_blocked_threads(e: EvidenceItem) -> EvidenceItem:
    # Parse "thread: total=XXms, max_single=XXms, count=XX"
    blocks = re.findall(r"(\S+): total=(\d+)ms, max_single=(\d+)ms, count=(\d+)", e.summary)
    parts = [e.summary]
    for thread, total, max_single, count in blocks[:3]:
        total_ms = int(total)
        max_ms = int(max_single)
        cnt = int(count)
        if max_ms > 100:
            parts.append(f"⚠️ {thread} 单次最长阻塞 {max_ms}ms，可能存在严重的锁竞争或 Binder 超时")
        elif max_ms > 16:
            parts.append(f"→ {thread} 单次最长阻塞 {max_ms}ms，超过单帧预算")
        if cnt > 100:
            parts.append(f"→ {thread} 阻塞 {cnt} 次，频率过高，检查是否有不必要的同步等待")

    return EvidenceItem(title=e.title, summary="\n".join(parts))


def _interpret_frame_rhythm(e: EvidenceItem) -> EvidenceItem:
    parts = [e.summary]
    over33 = re.search(r"(\d+) over 33ms", e.summary)
    over16 = re.search(r"(\d+) over 16ms", e.summary)
    if over33 and int(over33.group(1)) > 0:
        parts.append(f"⚠️ {over33.group(1)} 帧超过 33ms（2 倍帧预算），用户可感知明显卡顿")
    elif over16 and int(over16.group(1)) > 0:
        parts.append(f"→ {over16.group(1)} 帧超过 16ms，在 60Hz 设备上会掉帧")

    return EvidenceItem(title=e.title, summary="\n".join(parts))


def _interpret_binder(e: EvidenceItem) -> EvidenceItem:
    parts = [e.summary]
    matches = re.findall(r"(\S+): (\d+) calls, total=(\d+)ms, max=(\d+)ms", e.summary)
    for thread, calls, total, max_ms in matches[:3]:
        if int(max_ms) > 50:
            parts.append(f"⚠️ {thread} 单次 Binder 最长 {max_ms}ms，严重影响主线程响应")
        elif int(max_ms) > 16:
            parts.append(f"→ {thread} 单次 Binder 最长 {max_ms}ms，超过帧预算")
        if int(calls) > 20:
            parts.append(f"→ {thread} 调用 {calls} 次，考虑合并请求或缓存结果")

    return EvidenceItem(title=e.title, summary="\n".join(parts))


def _interpret_causal_chain(e: EvidenceItem) -> EvidenceItem:
    # Frame causal chain already has structured info, just add severity
    parts = [e.summary]
    dur_match = re.search(r"(\d+)ms", e.summary)
    if dur_match and int(dur_match.group(1)) > 50:
        parts.append("⚠️ 严重掉帧，需要优先排查")

    return EvidenceItem(title=e.title, summary="\n".join(parts))


_INTERPRETERS = {
    "Thread state distribution": _interpret_thread_state,
    "Long slices": _interpret_long_slices,
    "Scheduling delay": _interpret_scheduling_delay,
    "Blocked threads": _interpret_blocked_threads,
    "Frame rhythm": _interpret_frame_rhythm,
    "Binder transactions": _interpret_binder,
    "Frame causal chain": _interpret_causal_chain,
}
