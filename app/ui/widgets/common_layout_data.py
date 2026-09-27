from app.helpers.typing_helper import LayoutDictTypes
import app.ui.widgets.actions.layout_actions as layout_actions
import app.ui.widgets.actions.control_actions as control_actions

COMMON_LAYOUT_DATA: LayoutDictTypes = {
    # 'Face Compare':{
    #     'ViewFaceMaskEnableToggle':{
    #         'level': 1,
    #         'label': 'View Face Mask',
    #         'default': False,
    #         'help': 'Show Face Mask',
    #         'exec_function': layout_actions.fit_image_to_view_onchange,
    #         'exec_function_args': [],
    #     },
    #     'ViewFaceCompareEnableToggle':{
    #         'level': 1,
    #         'label': 'View Face Compare',
    #         'default': False,
    #         'help': 'Show Face Compare',
    #         'exec_function': layout_actions.fit_image_to_view_onchange,
    #         'exec_function_args': [],
    #     },
    # },
    'Face Restorer': {
        'FaceRestorerEnableToggle': {
            'level': 1,
            'label': '启用面部修复',
            'default': False,
            'help': '启用面部修复模型，以提升交换后面部的质量。'
        },
        'FaceRestorerTypeSelection': {
            'level': 2,
            'label': '修复类型',
            'options': ['GFPGAN-v1.4', 'GFPGAN-1024', 'CodeFormer', 'GPEN-256', 'GPEN-512', 'GPEN-1024', 'GPEN-2048', 'RestoreFormer++', 'VQFR-v2'],
            'default': 'GFPGAN-v1.4',
            'parentToggle': 'FaceRestorerEnableToggle',
            'requiredToggleValue': True,
            'help': '选择面部修复的模型类型。'
        },
        'FaceRestorerDetTypeSelection': {
            'level': 2,
            'label': '对齐方式',
            'options': ['Original', 'Blend', 'Reference'],
            'default': 'Original',
            'parentToggle': 'FaceRestorerEnableToggle',
            'requiredToggleValue': True,
            'help': '选择修复面部时将其恢复到原始位置、混合位置或参考位置的对齐方法。'
        },
        'FaceFidelityWeightDecimalSlider': {
            'level': 2,
            'label': '保真度权重',
            'min_value': '0.0',
            'max_value': '1.0',
            'default': '0.9',
            'decimals': 1,
            'step': 0.1,
            'parentToggle': 'FaceRestorerEnableToggle',
            'requiredToggleValue': True,
            'help': '调整保真度权重，控制修复时保留原始面部细节的程度。'
        },
        'FaceRestorerBlendSlider': {
            'level': 2,
            'label': '混合比例',
            'min_value': '0',
            'max_value': '100',
            'default': '100',
            'step': 1,
            'parentToggle': 'FaceRestorerEnableToggle',
            'requiredToggleValue': True,
            'help': '控制修复后的面部与交换面部之间的混合比例。'
        },
        'FaceRestorerEnable2Toggle': {
            'level': 1,
            'label': '启用面部修复 2',
            'default': False,
            'help': '启用第二个面部修复模型，以提升交换后面部的质量。'
        },
        'FaceRestorerType2Selection': {
            'level': 2,
            'label': '修复类型',
            'options': ['GFPGAN-v1.4', 'GFPGAN-1024', 'CodeFormer', 'GPEN-256', 'GPEN-512', 'GPEN-1024', 'GPEN-2048', 'RestoreFormer++', 'VQFR-v2'],
            'default': 'GFPGAN-v1.4',
            'parentToggle': 'FaceRestorerEnable2Toggle',
            'requiredToggleValue': True,
            'help': '选择面部修复的模型类型。'
        },
        'FaceRestorerDetType2Selection': {
            'level': 2,
            'label': '对齐方式',
            'options': ['Original', 'Blend', 'Reference'],
            'default': 'Original',
            'parentToggle': 'FaceRestorerEnable2Toggle',
            'requiredToggleValue': True,
            'help': '选择修复面部时将其恢复到原始位置、混合位置或参考位置的对齐方法。'
        },
        'FaceFidelityWeight2DecimalSlider': {
            'level': 2,
            'label': '保真度权重',
            'min_value': '0.0',
            'max_value': '1.0',
            'default': '0.9',
            'decimals': 1,
            'step': 0.1,
            'parentToggle': 'FaceRestorerEnable2Toggle',
            'requiredToggleValue': True,
            'help': '调整保真度权重，控制修复时保留原始面部细节的程度。'
        },
        'FaceRestorerBlend2Slider': {
            'level': 2,
            'label': '混合比例',
            'min_value': '0',
            'max_value': '100',
            'default': '100',
            'step': 1,
            'parentToggle': 'FaceRestorerEnable2Toggle',
            'requiredToggleValue': True,
            'help': '控制修复后的面部与交换面部之间的混合比例。'
        },
        'FaceExpressionEnableToggle': {
            'level': 1,
            'label': '启用面部表情修复',
            'default': False,
            'help': '启用 LivePortrait 面部表情模型，以在交换后恢复面部表情。'
        },
        'FaceExpressionCropScaleDecimalSlider': {
            'level': 2,
            'label': '裁剪比例',
            'min_value': '1.80',
            'max_value': '3.00',
            'default': '2.30',
            'step': 0.05,
            'decimals': 2,
            'parentToggle': 'FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '调整裁剪比例，增大值以更远距离捕获面部。'
        },
        'FaceExpressionVYRatioDecimalSlider': {
            'level': 2,
            'label': 'VY比例',
            'min_value': '-0.125',
            'max_value': '-0.100',
            'default': '-0.125',
            'step': 0.001,
            'decimals': 3,
            'parentToggle': 'FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '调整裁剪比例的 VY 值，增大值以更远距离捕获面部。'
        },
        'FaceExpressionFriendlyFactorDecimalSlider': {
            'level': 2,
            'label': '表情友好系数',
            'min_value': '0.0',
            'max_value': '1.0',
            'default': '1.0',
            'decimals': 1,
            'step': 0.1,
            'parentToggle': 'FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '控制驱动面部与交换面部之间的表情相似度。'
        },
        'FaceExpressionAnimationRegionSelection': {
            'level': 2,
            'label': '动画区域',
            'options': ['all', 'eyes', 'lips'],
            'default': 'all',
            'parentToggle': 'FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '选择修复过程中涉及的面部区域。'
        },
        'FaceExpressionNormalizeLipsEnableToggle': {
            'level': 2,
            'label': '标准化唇部',
            'default': True,
            'parentToggle': 'FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '在面部修复过程中标准化唇部。'
        },
        'FaceExpressionNormalizeLipsThresholdDecimalSlider': {
            'level': 3,
            'label': '标准化唇部阈值',
            'min_value': '0.00',
            'max_value': '1.00',
            'default': '0.03',
            'decimals': 2,
            'step': 0.01,
            'parentToggle': 'FaceExpressionNormalizeLipsEnableToggle & FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '标准化唇部的阈值。'
        },
        'FaceExpressionRetargetingEyesEnableToggle': {
            'level': 2,
            'label': '重定向眼神',
            'default': False,
            'parentToggle': 'FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '在面部修复过程中调整或重定向眼神或眼部运动。它会覆盖动画区域设置，即动画区域将被忽略。'
        },
        'FaceExpressionRetargetingEyesMultiplierDecimalSlider': {
            'level': 3,
            'label': '眼神重定向倍数',
            'min_value': '0.00',
            'max_value': '2.00',
            'default': '1.00',
            'decimals': 2,
            'step': 0.01,
            'parentToggle': 'FaceExpressionRetargetingEyesEnableToggle & FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '眼神重定向的倍数值。'
        },
        'FaceExpressionRetargetingLipsEnableToggle': {
            'level': 2,
            'label': '重定向唇部',
            'default': False,
            'parentToggle': 'FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '在面部修复过程中调整或修改唇部的位置、形状或运动。它会覆盖动画区域设置，即动画区域将被忽略。'
        },
        'FaceExpressionRetargetingLipsMultiplierDecimalSlider': {
            'level': 3,
            'label': '唇部重定向倍数',
            'min_value': '0.00',
            'max_value': '2.00',
            'default': '1.00',
            'decimals': 2,
            'step': 0.01,
            'parentToggle': 'FaceExpressionRetargetingLipsEnableToggle & FaceExpressionEnableToggle',
            'requiredToggleValue': True,
            'help': '唇部重定向的倍数值。'
        },
    },
    'ReF-LDM 去噪器': {
        'ReferenceKVTensorsSelection': {
            'level': 1, # Or your desired layout level
            'widget_type': 'SelectionBox',
            'label': '参考 K/V 张量',
            'control_name': 'ReferenceKVTensorsSelection',
            'options': [], # Will be populated by _populate_reference_kv_tensors
            'default': "", # Or a default filename if applicable
            # Add any 'condition_control' or 'parentToggle' if needed
            'help': '选择参考 K/V 张量文件（*.pt），文件须位于 "model_assets/reference_kv_data/" 目录。',
            'exec_function': lambda mw, val: mw.handle_reference_kv_file_change(val), # Trigger loading on UI change
            'exec_function_args': [] # No extra args needed
        },
        'UseReferenceExclusivePathToggle': { # New ToggleButton
            'level': 1,
            'widget_type': 'ToggleButton',
            'label': '独占参考路径',
            'control_name': 'UseReferenceExclusivePathToggle',
            'default': False,
            'help': '启用后强制 UNet 仅使用参考 K/V 进行注意力计算，最大化参考特征的聚焦程度。'
        },
        'DenoiserBaseSeedSlider': {
            'level': 1,
            'widget_type': 'ParameterSlider',
            'label': '基础随机种子',
            'control_name': 'DenoiserBaseSeedSlider',
            'min_value': '0', 'max_value': '999999', 'default': '220', 'step': 1,
            'help': '为去噪器设置固定的基础随机种子。该种子将用于所有帧与两个去噪阶段，确保噪声模式一致。'
        },
        'DenoiserUNetEnableBeforeRestorersToggle': {
            'level': 1,
            'widget_type': 'ToggleButton',
            'label': '启用修复前去噪器',
            'control_name': 'DenoiserUNetEnableBeforeRestorersToggle',
            'default': False,
            'help': '启用基于 UNet 的图像去噪，在其他修复器之前应用于 512x512 对齐/换脸后的面部。',
            'exec_function': control_actions.handle_denoiser_state_change,
            'exec_function_args': ['DenoiserUNetEnableBeforeRestorersToggle'],
        },
        'DenoiserModeSelectionBefore': {
            'level': 2,
            'widget_type': 'SelectionBox',
            'label': '去噪器模式（修复前）',
            'control_name': 'DenoiserModeSelectionBefore',
            'options': ["Single Step (Fast)", "Full Restore (DDIM)"],
            'default': "Single Step (Fast)",
            'parentToggle': 'DenoiserUNetEnableBeforeRestorersToggle',
            'requiredToggleValue': True,
            'help': '修复前阶段的去噪模式。单步模式通常更快。'
        },
        'DenoiserSingleStepTimestepSliderBefore': {
            'level': 3,
            'widget_type': 'ParameterSlider',
            'label': '单步时间步 (t)（修复前）',
            'control_name': 'DenoiserSingleStepTimestepSliderBefore',
            'min_value': '1', 'max_value': '999', 'default': '1', 'step': 1,
            'parentToggle': 'DenoiserUNetEnableBeforeRestorersToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionBefore',
            'requiredSelectionValue': "Single Step (Fast)",
            'help': '单步去噪的时间步（修复前）。数值越小，添加/去除的噪声越少。'
        },
        'DenoiserDDIMStepsSliderBefore': {
            'level': 3,
            'widget_type': 'ParameterSlider',
            'label': 'DDIM 步数（修复前）',
            'control_name': 'DenoiserDDIMStepsSliderBefore',
            'min_value': '10', 'max_value': '200', 'default': '20', 'step': 10,
            'parentToggle': 'DenoiserUNetEnableBeforeRestorersToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionBefore',
            'requiredSelectionValue': "Full Restore (DDIM)",
            'help': "完整修复的 DDIM 步数（修复前）。步数越多细节越好，但速度越慢。"
        },
        'DenoiserCFGScaleDecimalSliderBefore': {
            'level': 3,
            'widget_type': 'ParameterDecimalSlider',
            'label': 'CFG 引导强度（修复前）',
            'control_name': 'DenoiserCFGScaleDecimalSliderBefore',
            'min_value': '1.0', 'max_value': '10.0', 'default': '1.0', 'step': 0.1, 'decimals': 1,
            'parentToggle': 'DenoiserUNetEnableBeforeRestorersToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionBefore',
            'requiredSelectionValue': "Full Restore (DDIM)",
            'help': "DDIM 的无分类器引导强度（修复前）。数值越高越贴近参考 K/V。"
        },
        'DenoiserAfterFirstRestorerToggle': {
            'level': 1,
            'widget_type': 'ToggleButton',
            'label': '启用首个修复器后去噪器',
            'control_name': 'DenoiserAfterFirstRestorerToggle',
            'default': False,
            'help': '在首个修复器之后再次应用 UNet 去噪器，使用相同的 UNet 模型与步数设置。',
            'exec_function': control_actions.handle_denoiser_state_change,
            'exec_function_args': ['DenoiserAfterFirstRestorerToggle'],
        },
        'DenoiserModeSelectionAfterFirst': {
            'level': 2,
            'widget_type': 'SelectionBox',
            'label': '去噪器模式（首次修复后）',
            'control_name': 'DenoiserModeSelectionAfterFirst',
            'options': ["Single Step (Fast)", "Full Restore (DDIM)"],
            'default': "Single Step (Fast)",
            'parentToggle': 'DenoiserAfterFirstRestorerToggle',
            'requiredToggleValue': True,
            'help': '首个修复器之后阶段的去噪模式。单步模式通常更快。'
        },
        'DenoiserSingleStepTimestepSliderAfterFirst': {
            'level': 3,
            'widget_type': 'ParameterSlider',
            'label': '单步时间步 (t)（首次修复后）',
            'control_name': 'DenoiserSingleStepTimestepSliderAfterFirst',
            'min_value': '1', 'max_value': '999', 'default': '1', 'step': 1, # Max value was 200
            'parentToggle': 'DenoiserAfterFirstRestorerToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionAfterFirst',
            'requiredSelectionValue': "Single Step (Fast)",
            'help': '单步去噪的时间步（首个修复器之后）。数值越小，添加/去除的噪声越少。'
        },
        'DenoiserDDIMStepsSliderAfterFirst': {
            'level': 3,
            'widget_type': 'ParameterSlider',
            'label': 'DDIM 步数（首次修复后）',
            'control_name': 'DenoiserDDIMStepsSliderAfterFirst',
            'min_value': '10', 'max_value': '200', 'default': '20', 'step': 10,
            'parentToggle': 'DenoiserAfterFirstRestorerToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionAfterFirst',
            'requiredSelectionValue': "Full Restore (DDIM)",
            'help': "完整修复的 DDIM 步数（首个修复器之后）。步数越多细节越好，但速度越慢。"
        },
        'DenoiserCFGScaleDecimalSliderAfterFirst': {
            'level': 3,
            'widget_type': 'ParameterDecimalSlider',
            'label': 'CFG 引导强度（首次修复后）',
            'control_name': 'DenoiserCFGScaleDecimalSliderAfterFirst',
            'min_value': '1.0', 'max_value': '10.0', 'default': '1.0', 'step': 0.1, 'decimals': 1,
            'parentToggle': 'DenoiserAfterFirstRestorerToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionAfterFirst',
            'requiredSelectionValue': "Full Restore (DDIM)",
            'help': "DDIM 的无分类器引导强度（首个修复器之后）。数值越高越贴近参考 K/V。"
        },
        'DenoiserAfterRestorersToggle': {
            'level': 1,
            'widget_type': 'ToggleButton',
            'label': '启用修复后去噪器',
            'control_name': 'DenoiserAfterRestorersToggle',
            'default': False,
            'help': '在面部修复器之后再次应用 UNet 去噪器，使用相同的 UNet 模型与步数设置。',
            'exec_function': control_actions.handle_denoiser_state_change,
            'exec_function_args': ['DenoiserAfterFirstRestorerToggle'],
        },
        'DenoiserModeSelectionAfter': {
            'level': 2,
            'widget_type': 'SelectionBox',
            'label': '去噪器模式（修复后）',
            'control_name': 'DenoiserModeSelectionAfter',
            'options': ["Single Step (Fast)", "Full Restore (DDIM)"],
            'default': "Single Step (Fast)",
            'parentToggle': 'DenoiserAfterRestorersToggle',
            'requiredToggleValue': True,
            'help': '修复器之后阶段的去噪模式。单步模式通常更快。'
        },
        'DenoiserSingleStepTimestepSliderAfter': {
            'level': 3,
            'widget_type': 'ParameterSlider',
            'label': '单步时间步 (t)（修复后）',
            'control_name': 'DenoiserSingleStepTimestepSliderAfter',
            'min_value': '1', 'max_value': '999', 'default': '1', 'step': 1, # Max value was 200
            'parentToggle': 'DenoiserAfterRestorersToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionAfter',
            'requiredSelectionValue': "Single Step (Fast)",
            'help': '单步去噪的时间步（修复器之后）。数值越小，添加/去除的噪声越少。'
        },
        'DenoiserDDIMStepsSliderAfter': {
            'level': 3,
            'widget_type': 'ParameterSlider',
            'label': 'DDIM 步数（修复后）',
            'control_name': 'DenoiserDDIMStepsSliderAfter',
            'min_value': '10', 'max_value': '200', 'default': '20', 'step': 10,
            'parentToggle': 'DenoiserAfterRestorersToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionAfter',
            'requiredSelectionValue': "Full Restore (DDIM)",
            'help': "完整修复的 DDIM 步数（修复器之后）。步数越多细节越好，但速度越慢。"
        },
        'DenoiserCFGScaleDecimalSliderAfter': {
            'level': 3,
            'widget_type': 'ParameterDecimalSlider',
            'label': 'CFG 引导强度（修复后）',
            'control_name': 'DenoiserCFGScaleDecimalSliderAfter',
            'min_value': '1.0', 'max_value': '10.0', 'default': '1.0', 'step': 0.1, 'decimals': 1,
            'parentToggle': 'DenoiserAfterRestorersToggle',
            'requiredToggleValue': True,
            'parentSelection': 'DenoiserModeSelectionAfter',
            'requiredSelectionValue': "Full Restore (DDIM)",
            'help': "DDIM 的无分类器引导强度（修复器之后）。数值越高越贴近参考 K/V。"
        }
    }
}
