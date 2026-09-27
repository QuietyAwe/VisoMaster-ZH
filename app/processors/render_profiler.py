"""渲染性能剖析器

轻量级分段计时工具，用于定位离线渲染的性能瓶颈。
通过 render_profiler 单例在渲染管线各阶段埋点，渲染结束时输出时间分解报告。

用法:
    from app.processors.render_profiler import render_profiler
    with render_profiler.measure('detect'):
        ...
"""

import threading
import time
from contextlib import contextmanager


class RenderProfiler:
    """线程安全的分段计时器。禁用时 measure() 几乎零开销。"""

    def __init__(self):
        self.enabled = False
        self._lock = threading.Lock()
        self._times: dict[str, float] = {}
        self._counts: dict[str, int] = {}

    def reset(self):
        with self._lock:
            self._times.clear()
            self._counts.clear()

    @contextmanager
    def measure(self, name: str):
        if not self.enabled:
            yield
            return
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt = time.perf_counter() - t0
            with self._lock:
                self._times[name] = self._times.get(name, 0.0) + dt
                self._counts[name] = self._counts.get(name, 0) + 1

    def record(self, name: str, dt: float):
        if not self.enabled:
            return
        with self._lock:
            self._times[name] = self._times.get(name, 0.0) + dt
            self._counts[name] = self._counts.get(name, 0) + 1

    def get_total(self, name: str) -> float:
        with self._lock:
            return self._times.get(name, 0.0)

    def build_report(self, total_frames: int, wall_time: float) -> str:
        """生成人类可读的时间分解报告"""
        with self._lock:
            times = dict(self._times)
            counts = dict(self._counts)

        lines = []
        lines.append('')
        lines.append('========== 渲染性能剖析 ==========')
        fps = total_frames / wall_time if wall_time > 0 else 0.0
        lines.append(f'总帧数: {total_frames}  总耗时: {wall_time:.1f}s  '
                     f'平均: {wall_time / max(total_frames, 1) * 1000:.1f}ms/帧 ({fps:.1f} FPS)')

        # 流水线层（渲染主循环视角）
        # 注：ai_total为各AI worker线程的累计耗时（并行时可超过墙钟）；
        # collect_wait是主循环按帧序收集结果的等待，并行生效时应明显小于ai_total。
        pipeline_keys = [
            ('decode_wait', '解码等待(流水线欠载)'),
            ('ai_total', 'AI处理(worker累计)'),
            ('collect_wait', '帧序收集等待(并行收益)'),
            ('encode_wait', '编码背压等待'),
            ('frame_copy_tobytes', '帧拷贝/序列化'),
        ]
        ai_total = times.get('ai_total', 0.0)
        lines.append('')
        lines.append('--- 流水线时间分解 ---')
        for key, label in pipeline_keys:
            if key in times:
                avg = times[key] / max(counts.get(key, 1), 1) * 1000
                pct = times[key] / wall_time * 100 if wall_time > 0 else 0.0
                lines.append(f'  {label:<22} {times[key]:8.2f}s  {avg:7.2f}ms/帧  占总时长 {pct:5.1f}%')

        # AI 处理内部分解
        ai_keys = [
            ('marker_update', '标记参数更新(model_lock)'),
            ('worker_create', 'FrameWorker创建/拷贝'),
            ('load_to_vram', '载入显存(H2D)'),
            ('project', 'VR投影crop'),
            ('detect', '人脸检测'),
            ('recognize', '人脸识别(特征提取)'),
            ('swap', '人脸交换'),
            ('edit_face', '编辑人脸'),
            ('enhance', '超分/增强'),
            ('stitch', 'VR缝合回写'),
            ('to_numpy', '回传内存(D2H)'),
            ('other_ai', '其他AI开销'),
        ]
        lines.append('')
        lines.append('--- AI处理内部分解 (占AI处理时间) ---')
        for key, label in ai_keys:
            if key in times:
                avg = times[key] / max(counts.get(key, 1), 1) * 1000
                pct = times[key] / ai_total * 100 if ai_total > 0 else 0.0
                lines.append(f'  {label:<22} {times[key]:8.2f}s  {avg:7.2f}ms/帧  占AI {pct:5.1f}%')

        # 诊断建议
        lines.append('')
        lines.append('--- 诊断 ---')
        hints = self._build_hints(times, wall_time, total_frames)
        lines.extend(hints)
        lines.append('==================================')
        return '\n'.join(lines)

    def _build_hints(self, times: dict, wall_time: float, total_frames: int) -> list[str]:
        hints = []
        if wall_time <= 0 or total_frames <= 0:
            return ['  (无有效数据)']

        ai_total = times.get('ai_total', 0.0)
        decode_wait = times.get('decode_wait', 0.0)
        encode_wait = times.get('encode_wait', 0.0)

        if encode_wait / wall_time > 0.15:
            hints.append('  [编码瓶颈] 编码背压等待占比高：编码器跟不上AI出帧速度，'
                         '可尝试降低编码质量要求或换更快preset')
        if decode_wait / wall_time > 0.15:
            hints.append('  [解码瓶颈] 解码等待占比高：CPU解码跟不上，'
                         '可尝试ffmpeg硬解(h264_cuvid)或降低预读压力')
        collect_wait = times.get('collect_wait', 0.0)
        ai_total_all = times.get('ai_total', 0.0)
        if ai_total_all > 0 and collect_wait > 0:
            par_gain = 1.0 - collect_wait / ai_total_all
            if par_gain > 0.1:
                hints.append(f'  [并行生效] AI并行化带来约{par_gain * 100:.0f}%加速'
                             '（帧序收集等待远低于worker累计耗时）')
            elif wall_time > 0 and ai_total_all / wall_time < 1.1:
                hints.append('  [并行未生效] 收集等待≈worker累计耗时：GPU已饱和或并行度不足，'
                             '可尝试增大"线程数"设置')

        if ai_total > 0:
            stage_share = {
                'detect': times.get('detect', 0.0),
                'swap': times.get('swap', 0.0),
                'enhance': times.get('enhance', 0.0),
                'recognize': times.get('recognize', 0.0),
                'load_to_vram': times.get('load_to_vram', 0.0),
                'to_numpy': times.get('to_numpy', 0.0),
            }
            top = max(stage_share, key=stage_share.get)
            top_pct = stage_share[top] / ai_total * 100
            top_labels = {
                'detect': '人脸检测', 'swap': '人脸交换', 'enhance': '超分/增强',
                'recognize': '人脸识别', 'load_to_vram': 'H2D传输', 'to_numpy': 'D2H传输',
            }
            if top_pct > 30:
                hints.append(f'  [AI内最大耗时] {top_labels[top]}占AI处理 {top_pct:.0f}%，是推理侧主要开销')
                if top == 'detect':
                    hints.append('      → 可考虑：降低检测分辨率、关闭AutoRotation(4角度=4倍检测)、')
                    hints.append('        或对非关键帧做隔帧检测')
                elif top == 'enhance':
                    hints.append('      → 可考虑：降低增强强度/换轻量模型，或仅对关键帧增强')
                elif top == 'swap':
                    hints.append('      → 可考虑：换更快的Swap模型，或开启FP16推理')
                elif top in ('load_to_vram', 'to_numpy'):
                    hints.append('      → 传输占比高：说明GPU算得快、喂不饱，'
                                 '可用pinned memory + 多线程预取进一步优化')

            xfer = stage_share['load_to_vram'] + stage_share['to_numpy']
            if ai_total > 0 and xfer / ai_total > 0.15:
                hints.append(f'  [传输开销] H2D+D2H占AI处理 {xfer / ai_total * 100:.0f}%，存在CPU↔GPU往返瓶颈')

        if not hints:
            hints.append('  各阶段均衡；若GPU利用率仍低，检查是否多线程争用model_lock或GIL')
        return hints


# 全局单例
render_profiler = RenderProfiler()
