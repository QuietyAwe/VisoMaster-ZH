"""
视频区间离线渲染线程
用于在后台执行AI换脸渲染并输出带音频的视频文件
"""
import os
import queue
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
import torch
from PySide6.QtCore import QThread, Signal

from app.processors.workers.frame_worker import FrameWorker
import app.helpers.miscellaneous as misc_helpers

if TYPE_CHECKING:
    from app.ui.main_ui import MainWindow


class RenderThread(QThread):
    """后台渲染线程，执行视频区间的AI换脸渲染"""
    
    # 信号定义
    progress_signal = Signal(int, str)  # 进度百分比, 预估剩余时间文本
    finished_signal = Signal(str)       # 输出文件路径
    error_signal = Signal(str)          # 错误信息
    
    def __init__(self, video_path: str, start_frame: int, end_frame: int, 
                 output_folder: str, main_window: 'MainWindow'):
        super().__init__()
        self.video_path = video_path
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.output_folder = output_folder
        self.main_window = main_window
        self.is_cancelled = False
        
        # FFmpeg子进程
        self.recording_sp: subprocess.Popen | None = None
        self.temp_file = ''
        
        # P1: 异步编码管道（编码线程与AI推理重叠执行）
        # 队列深度延迟到run()按帧字节自适应（8K大帧自动收窄，防缓冲内存爆增）
        self.frame_write_queue: queue.Queue = queue.Queue(maxsize=6)
        self.writer_thread: threading.Thread | None = None
        self.writer_error: Exception | None = None
        
        # 进度信号节流状态
        self._last_progress_emit = 0.0
        self._last_progress_percent = -1
        
        # 渲染统计
        self.start_time = 0.0
        self.frames_processed = 0
        self.total_frames = end_frame - start_frame + 1
        
        # 线程局部FrameWorker缓存（并行worker各持有一份，避免共享实例竞争）
        self._worker_tls = threading.local()
        
    def run(self):
        """渲染主循环（P1三级流水线：解码线程 → AI推理 → 编码线程，各阶段重叠执行）"""
        cap = None
        reader_thread: threading.Thread | None = None
        frame_read_queue: queue.Queue = queue.Queue(maxsize=4)
        from app.processors.render_profiler import render_profiler
        render_profiler.enabled = True
        render_profiler.reset()
        try:
            self.start_time = time.perf_counter()
            
            # 1. 打开独立视频流
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.error_signal.emit(f"无法打开视频文件: {self.video_path}")
                return
            
            # 获取视频信息
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0
            
            # Seek到开始帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
            
            # 2. 读取第一帧以获取尺寸（用于创建FFmpeg管道）
            ret, first_frame = cap.read()
            if not ret:
                self.error_signal.emit(f"无法读取起始帧: {self.start_frame}")
                cap.release()
                return
            
            # 重置到开始位置
            cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
            
            # 2.5 队列深度按帧字节自适应：每队列缓冲预算256MB（8K约100MB/帧→深度2，1080p→深度6）
            frame_bytes = int(first_frame.shape[0]) * int(first_frame.shape[1]) * 3
            queue_budget = 256 * 1024 * 1024
            queue_depth = max(2, min(6, queue_budget // max(frame_bytes, 1)))
            frame_read_queue = queue.Queue(maxsize=queue_depth)
            self.frame_write_queue = queue.Queue(maxsize=queue_depth)
            print(f"渲染队列深度: {queue_depth} (帧大小 {frame_bytes / 1024 / 1024:.1f}MB)")
            
            # 3. 编码管道与编码线程延迟到首帧处理后创建（画面增强会改变输出尺寸，
            #    管道必须按处理后帧的实际尺寸配置，与video_processor的处理一致）
            
            # 4. 启动解码线程（预读帧，解码与AI推理重叠）
            reader_thread = threading.Thread(
                target=self._reader_loop,
                args=(cap, frame_read_queue),
                name="RenderReader", daemon=True,
            )
            reader_thread.start()
            
            # 5. AI推理：有序并行窗口（N个worker并发推理，严格按帧序收集交付编码）
            #    并行度跟随"线程数"设置（与预览路径一致），最多3路：GPU是瓶颈，再多收益极小
            #    而显存占用线性增长（每在途帧一套完整中间张量）
            max_workers = max(1, min(int(self.main_window.video_processor.num_threads), 3))
            print(f"渲染AI并行度: {max_workers} 线程")
            window: deque = deque()  # (frame_num, Future)，按帧序排列
            window_limit = max_workers  # 首帧后按帧字节收窄（8K大帧防在途缓冲爆显存/内存）
            
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='RenderAI') as pool:
                while True:
                    if self.is_cancelled:
                        break
                    if self.writer_error is not None:
                        raise RuntimeError(self._encode_error_message())
                    
                    # 在途帧达上限：先按帧序收集最旧结果（保序+背压）
                    if len(window) >= window_limit:
                        self._collect_result(window.popleft(), fps, queue_budget)
                        continue
                    
                    # [剖析] 解码等待：取不到帧说明解码线程供给不足
                    t0 = time.perf_counter()
                    try:
                        item = frame_read_queue.get(timeout=0.2)
                    except queue.Empty:
                        render_profiler.record('decode_wait', time.perf_counter() - t0)
                        continue
                    render_profiler.record('decode_wait', time.perf_counter() - t0)
                    
                    if item is None:  # 解码线程结束哨兵
                        break
                    frame_num, frame = item
                    if frame_num == self.start_frame:
                        # 在途帧数受内存约束：每个在途帧持有一套完整输入+输出缓冲
                        frame_bytes = int(frame.shape[0]) * int(frame.shape[1]) * 3
                        window_limit = max(1, min(max_workers, queue_budget // max(frame_bytes, 1)))
                        print(f"渲染并行窗口: {window_limit} 帧在途 (帧大小 {frame_bytes / 1024 / 1024:.1f}MB)")
                    # 派发：标记参数在派发线程按帧序解析并快照，worker间零共享
                    window.append((frame_num, self._submit_frame(pool, frame, frame_num)))
                
                # 收尾：按帧序排空在途结果
                while window and not self.is_cancelled:
                    self._collect_result(window.popleft(), fps, queue_budget)
                # 取消/异常路径：静默回收剩余Future，避免未取回异常的噪声日志
                while window:
                    _, leftover = window.popleft()
                    try:
                        leftover.result()
                    except Exception:
                        pass
            
            # 6. 收尾：通知编码线程结束并等待其关闭管道
            self._finish_writer()
            if reader_thread is not None:
                reader_thread.join(timeout=3.0)
            cap.release()
            
            # 渲染结束后统一释放显存缓存（每帧调用会强制同步并重建缓存池，严重拖慢渲染）
            torch.cuda.empty_cache()
            
            # 输出性能剖析报告
            wall_time = time.perf_counter() - self.start_time
            print(render_profiler.build_report(self.frames_processed, wall_time))
            render_profiler.enabled = False
            
            if self.writer_error is not None:
                raise RuntimeError(self._encode_error_message())
            
            if self.is_cancelled:
                self._cleanup_cancelled()
                return
            
            self._finalize_output(fps)
            
        except Exception as e:
            self.is_cancelled = True
            self._finish_writer()
            if reader_thread is not None:
                reader_thread.join(timeout=3.0)
            if cap is not None:
                cap.release()
            self.error_signal.emit(f"渲染过程中发生错误: {str(e)}")
            self._cleanup_cancelled("渲染失败")
    
    def _reader_loop(self, cap: cv2.VideoCapture, frame_read_queue: queue.Queue):
        """解码线程：顺序读取帧并填入限长队列（队满时阻塞=背压，防内存溢出）"""
        try:
            for frame_num in range(self.start_frame, self.end_frame + 1):
                if self.is_cancelled:
                    break
                ret, frame = cap.read()
                if not ret:
                    print(f"警告: 无法读取帧 {frame_num}，渲染提前结束")
                    break
                # BGR→RGB转换在解码线程完成：cv2转换释放GIL且输出C连续，与AI推理真并行
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                while not self.is_cancelled:
                    try:
                        frame_read_queue.put((frame_num, frame), timeout=0.2)
                        break
                    except queue.Full:
                        continue
        except Exception as e:
            print(f"解码线程异常: {e}")
        finally:
            # 哨兵：通知推理主循环解码结束
            # 必须可靠送达（队满时阻塞重试），否则主循环会永远等待；
            # 取消场景下主循环已退出，无需投递
            while not self.is_cancelled:
                try:
                    frame_read_queue.put(None, timeout=0.2)
                    break
                except queue.Full:
                    continue
    
    def _encode_error_message(self) -> str:
        """构造编码失败的错误信息（附FFmpeg stderr末尾日志，便于定位原因）"""
        tail = "\n".join(self._ffmpeg_stderr_tail[-10:]) if getattr(self, '_ffmpeg_stderr_tail', None) else ""
        reason = str(self.writer_error) if self.writer_error is not None else \
            f"FFmpeg编码进程异常退出 (返回码 {self.recording_sp.returncode if self.recording_sp else 'N/A'})"
        msg = f"视频编码失败: {reason}"
        if tail:
            msg += f"\nFFmpeg错误日志:\n{tail}"
        return msg
    
    def _writer_loop(self):
        """编码线程：从队列取帧序列化并写入FFmpeg管道，编码与AI推理重叠执行"""
        from app.processors.render_profiler import render_profiler
        try:
            while True:
                item = self.frame_write_queue.get()
                if item is None:  # 哨兵：正常结束
                    break
                if self.is_cancelled:
                    continue  # 取消时丢弃剩余帧，快速退出
                if self.recording_sp and self.recording_sp.stdin:
                    t0 = time.perf_counter()
                    # C连续帧用memoryview零拷贝写入；仅在异常非连续时才tobytes兜底
                    if isinstance(item, np.ndarray):
                        payload = memoryview(item) if item.flags['C_CONTIGUOUS'] else item.tobytes()
                    else:
                        payload = item
                    render_profiler.record('frame_copy_tobytes', time.perf_counter() - t0)
                    self.recording_sp.stdin.write(payload)
        except Exception as e:
            self.writer_error = e
        finally:
            # 编码线程独占stdin生命周期：写入端关闭后FFmpeg才会完成编码
            try:
                if self.recording_sp and self.recording_sp.stdin:
                    self.recording_sp.stdin.close()
            except Exception:
                pass
    
    def _finish_writer(self):
        """通知编码线程收尾并等待其退出（含取消时的队列清空）"""
        if self.writer_thread is None:
            return
        if self.is_cancelled:
            # 取消：清空积压帧，让编码线程尽快收到哨兵
            try:
                while True:
                    self.frame_write_queue.get_nowait()
            except queue.Empty:
                pass
        while self.writer_thread.is_alive():
            try:
                self.frame_write_queue.put(None, timeout=0.2)
                break
            except queue.Full:
                continue
        self.writer_thread.join(timeout=10.0)
    
    def _submit_frame(self, pool: ThreadPoolExecutor, frame_rgb: np.ndarray, frame_num: int) -> Future:
        """派发一帧AI处理任务。
        
        标记参数的解析与快照在派发线程按帧序执行（这是有序并行的关键）：
        每帧获得独立的parameters/control副本，worker之间零共享、零竞态。
        """
        from app.processors.render_profiler import render_profiler
        
        # 更新参数从标记（如果有）；markers为空时短路，省去逐帧model_lock加锁开销
        t0 = time.perf_counter()
        if self.main_window.markers:
            with self.main_window.models_processor.model_lock:
                from app.ui.widgets.actions import video_control_actions
                video_control_actions.update_parameters_and_control_from_marker(
                    self.main_window, frame_num
                )
        parameters = self.main_window.parameters.copy()
        control = self.main_window.control.copy()
        use_ai = (self.main_window.swapfacesButton.isChecked() or
                  self.main_window.editFacesButton.isChecked() or
                  control['FrameEnhancerEnableToggle'] or
                  control.get('VR180ModeEnableToggle', False))  # VR180 模式始终处理（与 FrameWorker.run 一致）
        render_profiler.record('marker_update', time.perf_counter() - t0)
        
        return pool.submit(
            self._process_frame_task, frame_rgb, frame_num, parameters, control, use_ai
        )
    
    def _process_frame_task(self, frame_rgb: np.ndarray, frame_num: int,
                            parameters: dict, control: dict, use_ai: bool) -> np.ndarray:
        """worker线程执行的AI处理任务（复用FrameWorker逻辑）；frame_rgb须为C连续的RGB帧。
        
        每个worker线程持有独立的FrameWorker实例（线程局部缓存），互不共享。
        """
        from app.processors.render_profiler import render_profiler
        
        t0 = time.perf_counter()
        worker = getattr(self._worker_tls, 'worker', None)
        if worker is None:
            worker = FrameWorker(
                frame_rgb,
                self.main_window,
                frame_num,
                None,  # frame_queue 在离线渲染时不使用
                is_single_frame=True
            )
            worker.is_view_face_compare = False
            worker.is_view_face_mask = False
            self._worker_tls.worker = worker
        worker.frame = frame_rgb
        worker.frame_number = frame_num
        worker.parameters = parameters
        worker.control_override = control
        render_profiler.record('worker_create', time.perf_counter() - t0)
        
        t0 = time.perf_counter()
        if use_ai:
            processed_frame = worker.process_frame()
        else:
            # 如果没有启用任何处理，直接返回BGR格式
            # cv2转换输出C连续（负步长视图会让下游序列化退化为逐字节收集，实测慢20倍）
            processed_frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        render_profiler.record('ai_total', time.perf_counter() - t0)
        return processed_frame
    
    def _collect_result(self, entry: tuple, fps: float, queue_budget: int):
        """按帧序收集一个AI处理结果并投入编码队列（保序交付，输出帧序严格不变）"""
        from app.processors.render_profiler import render_profiler
        frame_num, future = entry
        
        # 等待该帧完成；其余在途帧由各自worker并行推进
        t0 = time.perf_counter()
        processed_frame = future.result()
        render_profiler.record('collect_wait', time.perf_counter() - t0)
        
        # 首帧处理后按实际输出尺寸创建编码管道（增强/修复可能改变尺寸）并启动编码线程
        if self.writer_thread is None:
            # 写队列按处理后帧大小重估深度（如4x增强会把帧放大16倍）
            out_bytes = int(processed_frame.shape[0]) * int(processed_frame.shape[1]) * 3
            self.frame_write_queue = queue.Queue(
                maxsize=max(2, min(6, queue_budget // max(out_bytes, 1)))
            )
            self._create_ffmpeg_subprocess(processed_frame.shape, fps)
            self.writer_thread = threading.Thread(
                target=self._writer_loop, name="RenderWriter", daemon=True
            )
            self.writer_thread.start()
        
        # 投入编码队列（队满时阻塞=背压，同时检查取消）
        # 序列化(tobytes)在编码线程执行，与AI推理重叠
        t0 = time.perf_counter()
        while not self.is_cancelled:
            try:
                self.frame_write_queue.put(processed_frame, timeout=0.2)
                break
            except queue.Full:
                if self.writer_error is not None:
                    raise RuntimeError(self._encode_error_message())
        render_profiler.record('encode_wait', time.perf_counter() - t0)
        
        # 更新进度
        self.frames_processed += 1
        self._update_progress()
    
    # NVENC 探测结果缓存（类级别，键为"编码器:宽x高"，避免每次渲染重复探测）
    _nvenc_probe_cache: dict[str, bool] = {}
    
    @classmethod
    def _is_nvenc_usable(cls, codec: str, width: int, height: int) -> bool:
        """按目标分辨率、使用与实际编码相同的参数探测指定NVENC编码器是否可用
        
        不同GPU代数对编码分辨率有上限（如H.264通常不超过4096宽），
        必须按实际分辨率探测，否则8K等超大分辨率会在编码器打开时报
        "No capable devices found"导致渲染失败。
        """
        key = f"{codec}:{width}x{height}"
        if key in cls._nvenc_probe_cache:
            return cls._nvenc_probe_cache[key]
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d=0.1",
                    "-c:v", codec, "-preset", "p5",
                    "-rc", "vbr", "-cq", "19", "-b:v", "0",
                    "-pix_fmt", "yuv420p",
                    "-f", "null", "-",
                ],
                capture_output=True,
                timeout=30,
            )
            usable = result.returncode == 0
        except Exception:
            usable = False
        if not usable:
            print(f"NVENC探测: {codec} 不支持 {width}x{height} 分辨率编码")
        cls._nvenc_probe_cache[key] = usable
        return usable
    
    def _create_ffmpeg_subprocess(self, frame_shape: tuple, fps: float):
        """创建FFmpeg子进程用于视频编码（优先NVIDIA硬件编码，按分辨率探测可用编码器）"""
        frame_height, frame_width, _ = frame_shape
        
        self.temp_file = r'temp_render_output.mp4'
        if Path(self.temp_file).is_file():
            os.remove(self.temp_file)
        
        common_args = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "rawvideo",             # 原始视频输入
            "-pix_fmt", "bgr24",          # 像素格式
            "-s", f"{frame_width}x{frame_height}",  # 分辨率
            "-r", str(fps),               # 帧率
            "-i", "pipe:",                # 从stdin输入
        ]
        
        # 按实际分辨率探测编码器：H.264 NVENC 有分辨率上限（8K会失败），
        # 超限时依次回退 hevc_nvenc（支持8K）→ libx264 软编码
        # 探测使用pad后的偶数分辨率，与实际编码参数一致
        probe_w = (frame_width + 1) // 2 * 2
        probe_h = (frame_height + 1) // 2 * 2
        if self._is_nvenc_usable("h264_nvenc", probe_w, probe_h):
            # NVIDIA硬件编码：编码任务卸载到GPU，CPU可专注AI前处理，大幅提升整体吞吐
            args = common_args + [
                "-vf", f"pad=ceil(iw/2)*2:ceil(ih/2)*2",  # yuv420p要求宽高为偶数
                "-c:v", "h264_nvenc",
                "-preset", "p5",          # 质量/速度均衡
                "-rc", "vbr",             # 可变码率
                "-cq", "19",              # 质量参数（约等于libx264 crf18）
                "-b:v", "0",              # 不限制码率上限，由cq控制质量
                "-pix_fmt", "yuv420p",
                self.temp_file
            ]
            encoder_name = "h264_nvenc (GPU硬件编码)"
        elif self._is_nvenc_usable("hevc_nvenc", probe_w, probe_h):
            # H.265硬件编码：支持8K等超大分辨率（H.264 NVENC超限时的GPU加速回退）
            args = common_args + [
                "-vf", f"pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "hevc_nvenc",
                "-tag:v", "hvc1",         # 提升播放器兼容性
                "-preset", "p5",
                "-rc", "vbr",
                "-cq", "19",
                "-b:v", "0",
                "-pix_fmt", "yuv420p",
                self.temp_file
            ]
            encoder_name = "hevc_nvenc (GPU硬件编码, H.265)"
        else:
            # 回退：libx264软编码
            args = common_args + [
                "-vf", f"pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuvj420p",
                "-c:v", "libx264",        # H.264编码
                "-crf", "18",             # 质量设置
                self.temp_file
            ]
            encoder_name = "libx264 (CPU软编码)"
        
        print(f"渲染编码器: {encoder_name} | 分辨率: {frame_width}x{frame_height}")
        self.recording_sp = subprocess.Popen(
            args, stdin=subprocess.PIPE, stderr=subprocess.PIPE
        )
        # 持续读取stderr防止管道堵塞，并保留末尾日志用于错误诊断
        self._ffmpeg_stderr_tail: list[str] = []
        self._stderr_thread = threading.Thread(
            target=self._drain_ffmpeg_stderr, name="RenderFFmpegStderr", daemon=True
        )
        self._stderr_thread.start()
    
    def _drain_ffmpeg_stderr(self):
        """持续读取FFmpeg stderr（防止管道写满阻塞编码），保留末尾若干行供报错使用"""
        sp = self.recording_sp
        if sp is None or sp.stderr is None:
            return
        try:
            for raw_line in sp.stderr:
                line = raw_line.decode('utf-8', errors='replace').rstrip()
                print(f"[ffmpeg] {line}")
                self._ffmpeg_stderr_tail.append(line)
                if len(self._ffmpeg_stderr_tail) > 30:
                    self._ffmpeg_stderr_tail.pop(0)
        except Exception:
            pass
    
    def _update_progress(self):
        """更新进度和预估时间（节流：百分比变化或间隔≥300ms才发射，消除信号风暴）"""
        now = time.perf_counter()
        percent = int((self.frames_processed / self.total_frames) * 100)
        if percent == self._last_progress_percent and (now - self._last_progress_emit) < 0.3:
            return
        self._last_progress_percent = percent
        self._last_progress_emit = now
        
        elapsed_time = now - self.start_time
        if self.frames_processed > 0:
            avg_time_per_frame = elapsed_time / self.frames_processed
            remaining_frames = self.total_frames - self.frames_processed
            remaining_time = avg_time_per_frame * remaining_frames
            
            # 格式化剩余时间
            if remaining_time < 60:
                time_str = f"{remaining_time:.1f}秒"
            elif remaining_time < 3600:
                minutes = int(remaining_time // 60)
                seconds = int(remaining_time % 60)
                time_str = f"{minutes}分{seconds}秒"
            else:
                hours = int(remaining_time // 3600)
                minutes = int((remaining_time % 3600) // 60)
                time_str = f"{hours}小时{minutes}分"
            
            self.progress_signal.emit(percent, time_str)
    
    def _finalize_output(self, fps: float):
        """完成输出，合并音频"""
        try:
            if self.recording_sp is None:
                raise RuntimeError("未产生任何渲染帧，无法生成输出文件")
            # stdin已由编码线程关闭（_finish_writer保证线程已退出），此处仅等待编码进程完成
            if self.recording_sp:
                self.recording_sp.wait()
                if self.recording_sp.returncode != 0:
                    raise RuntimeError(self._encode_error_message())
            
            # 计算音频时间范围
            start_time = self.start_frame / fps
            end_time = (self.end_frame + 1) / fps
            
            # 生成最终输出文件路径
            final_file_path = misc_helpers.get_output_file_path(
                self.video_path, self.output_folder
            )
            
            # 如果输出文件已存在，先删除
            if Path(final_file_path).is_file():
                os.remove(final_file_path)
            
            # 合并音频
            # 注意：用-t精确时长而非-shortest——AAC音频流实际时长常短于视频（编码粒度/延迟），
            # -shortest会按最短流截断砍掉视频尾帧（实测30帧只保留29帧）
            print("正在合并音频...")
            args = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-i", self.temp_file,
                "-ss", str(start_time), "-to", str(end_time),
                "-i", self.video_path,
                "-c", "copy",
                "-map", "0:v:0", "-map", "1:a:0?",
                "-t", str(end_time - start_time),
                final_file_path
            ]
            subprocess.run(args, check=False)
            
            # 删除临时文件
            if Path(self.temp_file).is_file():
                os.remove(self.temp_file)
            
            # 统计渲染时间
            total_time = time.perf_counter() - self.start_time
            avg_fps = self.frames_processed / total_time if total_time > 0 else 0
            
            print(f"\n渲染完成!")
            print(f"处理帧数: {self.frames_processed}")
            print(f"总耗时: {total_time:.2f}秒")
            print(f"平均FPS: {avg_fps:.2f}")
            print(f"输出文件: {final_file_path}")
            
            self.finished_signal.emit(final_file_path)
            
        except Exception as e:
            # 失败时同样清理临时文件，避免残留
            if self.temp_file and Path(self.temp_file).is_file():
                try:
                    os.remove(self.temp_file)
                except OSError:
                    pass
            self.error_signal.emit(f"输出视频时发生错误: {str(e)}")
    
    def _cleanup_cancelled(self, reason: str = "渲染已取消"):
        """清理渲染资源（取消或失败时调用）"""
        try:
            # stdin已由编码线程关闭，此处仅终止/等待编码进程
            if self.recording_sp:
                if self.recording_sp.poll() is None:
                    self.recording_sp.kill()
                self.recording_sp.wait()
            
            # 删除临时文件
            if self.temp_file and Path(self.temp_file).is_file():
                os.remove(self.temp_file)
            
            print(f"{reason}，临时文件已清理")
            
        except Exception as e:
            print(f"清理资源时发生错误: {str(e)}")
    
    def cancel(self):
        """取消渲染"""
        self.is_cancelled = True
