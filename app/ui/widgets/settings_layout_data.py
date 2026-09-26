from app.ui.widgets.actions import control_actions
import cv2
from app.helpers.typing_helper import LayoutDictTypes
SETTINGS_LAYOUT_DATA: LayoutDictTypes = {
    'Appearance': {
        'ThemeSelection': {
            'level': 1,
            'label': '主题',
            'options': ['Dark', 'Dark-Blue', 'Light'],
            'default': 'Dark',
            'help': '选择要使用的主题',
            'exec_function': control_actions.change_theme,
            'exec_function_args': [],
        },
    },
    'General': {
        'ProvidersPrioritySelection': {
            'level': 1,
            'label': '提供者优先级',
            'options': ['CUDA', 'TensorRT', 'TensorRT-Engine', 'CPU'],
            'default': 'CUDA',
            'help': '选择系统中使用的提供者优先级。',
            'exec_function': control_actions.change_execution_provider,
            'exec_function_args': [],
        },
        'nThreadsSlider': {
            'level': 1,
            'label': '线程数',
            'min_value': '1',
            'max_value': '30',
            'default': '2',
            'step': 1,
            'help': '设置播放和录制时的执行线程数。强烈依赖GPU显存。',
            'exec_function': control_actions.change_threads_number,
            'exec_function_args': [],
        },
    },
    'Video Playback Settings': {
        'VideoPlaybackCustomFpsToggle': {
            'level': 1,
            'label': '设置自定义视频播放帧率',
            'default': False,
            'help': '手动设置播放视频时使用的帧率',
            'exec_function': control_actions.set_video_playback_fps,
            'exec_function_args': [],
        },
        'VideoPlaybackCustomFpsSlider': {
            'level': 2,
            'label': '视频播放帧率',
            'min_value': '1',
            'max_value': '120',
            'default': '30',
            'parentToggle': 'VideoPlaybackCustomFpsToggle',
            'requiredToggleValue': True,
            'step': 1,
            'help': '设置视频播放时的最大帧率'
        },
        'LiveSoundSpeedDecimalSlider': {
            'level': 1,
            'label': 'Audio Playback Speed',
            'min_value': '0.50',
            'max_value': '2.00',
            'default': '1.00',
            'step': 0.01,
            'decimals': 2,
            'help': '[Experimental] Set the playback speed of the audio, when Live Sound is enabled'
        },
    },
    'Auto Swap':{
        'AutoSwapToggle': {
            'level': 1,
            'label': '自动交换',
            'default': False,
            'help': '加载视频/图像文件时，使用选定的源面部/嵌入自动交换所有面部'
        },
    },
    'Detectors': {
        'DetectorModelSelection': {
            'level': 1,
            'label': '面部检测模型',
            'options': ['RetinaFace', 'Yolov8', 'SCRFD', 'Yunet'],
            'default': 'RetinaFace',
            'help': '选择用于在输入图像或视频中检测面部的面部检测模型。'
        },
        'DetectorScoreSlider': {
            'level': 1,
            'label': '检测得分',
            'min_value': '1',
            'max_value': '100',
            'default': '50',
            'step': 1,
            'help': '设置面部检测的置信度得分阈值。值越高，检测越自信，但可能错过一些面部。'
        },
        'MaxFacesToDetectSlider': {
            'level': 1,
            'label': '最大检测面部数',
            'min_value': '1',
            'max_value': '50',
            'default': '20',
            'step': 1,     
            'help': '设置一帧中检测的最大面部数量'
   
        },
        'AutoRotationToggle': {
            'level': 1,
            'label': '自动旋转',
            'default': False,
            'help': '自动旋转输入以检测各种方向的面部。'
        },
        'ManualRotationEnableToggle': {
            'level': 1,
            'label': '手动旋转',
            'default': False,
            'help': '旋转面部检测器以更好地检测不同角度的面部。'
        },
        'ManualRotationAngleSlider': {
            'level': 2,
            'label': '旋转角度',
            'min_value': '0',
            'max_value': '270',
            'default': '0',
            'step': 90,
            'parentToggle': 'ManualRotationEnableToggle',
            'requiredToggleValue': True,
            'help': '设置为输入面部角度，以帮助检测躺下/倒挂等情况。角度按顺时针读取。'
        },
        'LandmarkDetectToggle': {
            'level': 1,
            'label': '启用关键点检测',
            'default': False,
            'help': '启用或禁用面部关键点检测，用于优化面部对齐。'
        },
        'LandmarkDetectModelSelection': {
            'level': 2,
            'label': '关键点检测模型',
            'options': ['5', '68', '3d68', '98', '106', '203', '478'],
            'default': '203',
            'parentToggle': 'LandmarkDetectToggle',
            'requiredToggleValue': True,
            'help': '选择关键点检测模型，不同模型检测的面部关键点数量不同。'
        },
        'LandmarkDetectScoreSlider': {
            'level': 2,
            'label': '关键点检测得分',
            'min_value': '1',
            'max_value': '100',
            'default': '50',
            'step': 1,
            'parentToggle': 'LandmarkDetectToggle',
            'requiredToggleValue': True,
            'help': '设置面部关键点检测的置信度得分阈值。'
        },
        'DetectFromPointsToggle': {
            'level': 2,
            'label': '从关键点检测',
            'default': False,
            'parentToggle': 'LandmarkDetectToggle',
            'requiredToggleValue': True,
            'help': '启用从指定关键点检测面部。'
        },
        'ShowLandmarksEnableToggle': {
            'level': 1,
            'label': '显示关键点',
            'default': False,
            'help': '实时显示关键点。'
        },
        'ShowAllDetectedFacesBBoxToggle': {
            'level': 1,
            'label': '显示边界框',
            'default': False,
            'help': '为帧中检测到的所有面部绘制边界框'
        }
    },
    'Face Tracking': {
        'TemporalStabilizationToggle': {
            'level': 1,
            'label': '时序稳定',
            'default': True,
            'help': '跨帧跟踪已锁定的面部：相似度平滑 + 双阈值迟滞，用于消除换脸在相似度阈值附近反复出现/消失的闪烁。关闭后完全恢复为逐帧独立判定。'
        },
        'KeypointSmoothingToggle': {
            'level': 2,
            'label': '关键点平滑',
            'default': True,
            'parentToggle': 'TemporalStabilizationToggle',
            'requiredToggleValue': True,
            'help': '使用 1€ 滤波器平滑面部关键点与仿射变换，静止时消除边缘抖动，快速运动时自动减小平滑以避免拖影。'
        },
        'KeypointSmoothingMinCutoffDecimalSlider': {
            'level': 3,
            'label': '最小截止频率',
            'min_value': '0.10',
            'max_value': '5.00',
            'default': '1.00',
            'decimals': 2,
            'step': 0.05,
            'parentToggle': 'KeypointSmoothingToggle',
            'requiredToggleValue': True,
            'help': '面部静止时的平滑强度。值越小越平滑（抖动越少），值越大越贴近检测结果。'
        },
        'KeypointSmoothingBetaDecimalSlider': {
            'level': 3,
            'label': '速度系数',
            'min_value': '0.001',
            'max_value': '0.200',
            'default': '0.010',
            'decimals': 3,
            'step': 0.005,
            'parentToggle': 'KeypointSmoothingToggle',
            'requiredToggleValue': True,
            'help': '面部运动速度对平滑强度的影响。值越大，快速转头/移动时越贴合当前帧（拖影越少，抖动越多）。'
        },
        'MaxMissedFramesSlider': {
            'level': 2,
            'label': '最大丢失帧数',
            'min_value': '0',
            'max_value': '10',
            'default': '2',
            'step': 1,
            'parentToggle': 'TemporalStabilizationToggle',
            'requiredToggleValue': True,
            'help': '允许面部连续丢失的帧数。在此范围内重新出现时会保持原有的锁定状态，超过后重新按阈值捕获。'
        }
    },
    'DFM Settings':{
        'MaxDFMModelsSlider':{
            'level': 1,
            'label': '最大DFM模型数量',
            'min_value': '1',
            'max_value': '5',
            'default': '1',
            'step': 1,
            'help': '设置内存中保留的最大DFM模型数量，请根据显存大小设置',
        }
    },
    'Frame Enhancer':{
        'FrameEnhancerEnableToggle':{
            'level': 1,
            'label': '启用帧增强',
            'default': False,
            'help': '启用视频输入的帧增强以提升视觉质量。'
        },
        'FrameEnhancerTypeSelection':{
            'level': 2,
            'label': '帧增强类型',
            'options': ['RealEsrgan-x2-Plus', 'RealEsrgan-x4-Plus', 'RealEsr-General-x4v3', 'BSRGan-x2', 'BSRGan-x4', 'UltraSharp-x4', 'UltraMix-x4', 'DDColor-Artistic', 'DDColor', 'DeOldify-Artistic', 'DeOldify-Stable', 'DeOldify-Video'],
            'default': 'RealEsrgan-x2-Plus',
            'parentToggle': 'FrameEnhancerEnableToggle',
            'requiredToggleValue': True,
            'help': '根据内容和分辨率需求选择要应用的帧增强类型。'
        },
        'FrameEnhancerBlendSlider': {
            'level': 2,
            'label': '混合',
            'min_value': '0',
            'max_value': '100',
            'default': '100',
            'step': 1,
            'parentToggle': 'FrameEnhancerEnableToggle',
            'requiredToggleValue': True,
            'help': '将增强结果混合回原始帧。'
        },
    },
    'Webcam Settings': {
        'WebcamMaxNoSelection': {
            'level': 2,
            'label': '网络摄像头最大数量',
            'options': ['1', '2', '3', '4', '5', '6'],
            'default': '1',
            'help': '选择允许用于面部交换的网络摄像头流的最大数量。'
        },
        'WebcamBackendSelection': {
            'level': 2,
            'label': '网络摄像头后端',
            'options': ['Default', 'DirectShow', 'MSMF', 'V4L', 'V4L2', 'GSTREAMER'],
            'default': 'Default',
            'help': '选择访问网络摄像头输入的后端。'
        },
        'WebcamMaxResSelection': {
            'level': 2,
            'label': '网络摄像头分辨率',
            'options': ['480x360', '640x480', '1280x720', '1920x1080', '2560x1440', '3840x2160'],
            'default': '1280x720',
            'help': '选择网络摄像头输入的最大分辨率。'
        },
        'WebCamMaxFPSSelection': {
            'level': 2,
            'label': '网络摄像头帧率',
            'options': ['23', '30', '60'],
            'default': '30',
            'help': '设置网络摄像头输入的最大每秒帧数（FPS）。'
        },
    },
    'Virtual Camera': {
        'SendVirtCamFramesEnableToggle': {
            'level': 1,
            'label': '发送帧到虚拟摄像头',
            'default': False,
            'help': '将交换后的视频/网络摄像头输出发送到虚拟摄像头，以便在外部应用程序中使用',
            'exec_function': control_actions.toggle_virtualcam,
            'exec_function_args': [],
        },
        'VirtCamBackendSelection': {
            'level': 1,
            'label': '虚拟摄像头后端',
            'options': ['obs', 'unitycapture'],
            'default': 'obs',
            'help': '根据你设置的虚拟摄像头选择后端',
            'parentToggle': 'SendVirtCamFramesEnableToggle',
            'requiredToggleValue': True,
            'exec_function': control_actions.enable_virtualcam,
            'exec_function_args': [],
        },
    },
    'Face Recognition': {
        'RecognitionModelSelection': {
            'level': 1,
            'label': '识别模型',
            'options': ['Inswapper128ArcFace', 'SimSwapArcFace', 'GhostArcFace', 'CSCSArcFace'],
            'default': 'Inswapper128ArcFace',
            'help': '选择用于比较面部相似度的ArcFace模型。'
        },
        'SimilarityTypeSelection': {
            'level': 1,
            'label': '交换相似度类型',
            'options': ['Opal', 'Pearl', 'Optimal'],
            'default': 'Opal',
            'help': '选择面部交换过程中用于面部检测和匹配的相似度计算类型。'
        },
    },
    'Embedding Merge Method':{
        'EmbMergeMethodSelection':{
            'level': 1,
            'label': '嵌入合并方法',
            'options': ['Mean','Median'],
            'default': 'Mean',
            'help': '选择合并面部嵌入的方法。"Mean"取平均值，"Median"取中间值，对异常值更稳健。'
        }
    },
    'Media Selection':{
        'TargetMediaFolderRecursiveToggle':{
            'level': 1,
            'label': '目标媒体包括子文件夹',
            'default': False,
            'help': '选择目标媒体文件夹时包括所有子文件夹中的文件'
        },
        'InputFacesFolderRecursiveToggle':{
            'level': 1,
            'label': '输入面部包括子文件夹',
            'default': False,
            'help': '选择输入面部文件夹时包括所有子文件夹中的文件'
        }
    }
}

CAMERA_BACKENDS = {
    'Default': cv2.CAP_ANY,
    'DirectShow': cv2.CAP_DSHOW,
    'MSMF': cv2.CAP_MSMF,
    'V4L': cv2.CAP_V4L,
    'V4L2': cv2.CAP_V4L2,
    'GSTREAMER': cv2.CAP_GSTREAMER,
}