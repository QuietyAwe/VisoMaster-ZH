
from typing import TYPE_CHECKING, Dict
import uuid

import numpy
import cv2
import torch
from torchvision.transforms import v2

import app.ui.widgets.actions.common_actions as common_widget_actions
from app.ui.widgets.actions import list_view_actions
import app.helpers.miscellaneous as misc_helpers
from app.ui.widgets.settings_layout_data import SETTINGS_LAYOUT_DATA

if TYPE_CHECKING:
    from app.ui.main_ui import MainWindow

def clear_target_faces(main_window: 'MainWindow', refresh_frame=True):
    if main_window.video_processor.processing:
        main_window.video_processor.stop_processing()
    main_window.targetFacesList.clear()
    for _, target_face in main_window.target_faces.items():
        target_face.deleteLater()
    main_window.target_faces = {}
    main_window.parameters = {}

    main_window.selected_target_face_id = False
    refresh_input_faces_usage_markers(main_window)
    # Set Parameter widget values to default
    common_widget_actions.set_widgets_values_using_face_id_parameters(main_window=main_window, face_id=False)
    if refresh_frame:
        common_widget_actions.refresh_frame(main_window=main_window)

    
def clear_input_faces(main_window: 'MainWindow'):
    main_window.inputFacesList.clear()
    for _, input_face in main_window.input_faces.items():
        input_face.deleteLater()
    main_window.input_faces = {}

    for _, target_face in main_window.target_faces.items():
        target_face.assigned_input_faces = {}
        target_face.calculate_assigned_input_embedding()
    refresh_input_faces_usage_markers(main_window)
    common_widget_actions.refresh_frame(main_window=main_window)

def clear_merged_embeddings(main_window: 'MainWindow'):
    main_window.inputEmbeddingsList.clear()
    for _, embed_button in main_window.merged_embeddings.items():
        embed_button.deleteLater()
    main_window.merged_embeddings = {}

    for _, target_face in main_window.target_faces.items():
        target_face.assigned_merged_embeddings = {}
        target_face.calculate_assigned_input_embedding()
    common_widget_actions.refresh_frame(main_window=main_window)

def uncheck_all_input_faces(main_window: 'MainWindow'):
    # Uncheck All other input faces 
    for _, input_face_button in main_window.input_faces.items():
        input_face_button.setChecked(False)

def refresh_target_face_colors(main_window: 'MainWindow'):
    """Give every existing target face its own colour, following the list order.

    Colours are (re)assigned from the current list instead of a global counter, so
    scanning more faces (which only appends to the list) can never exhaust the
    palette, and deleting a face keeps the remaining colours compact.
    """
    # Imported here to avoid a circular import at module load time.
    from app.ui.widgets import widget_components

    colors = widget_components.TARGET_FACE_COLORS
    for index, target_face in enumerate(main_window.target_faces.values()):
        target_face.set_color(colors[index % len(colors)])

def refresh_target_face_highlights(main_window: 'MainWindow'):
    """Highlight the target faces that use the input face under the mouse cursor.

    The white ring is a hover preview only: it disappears as soon as the pointer
    leaves the input face (or the card is hidden or removed).
    """
    if not main_window.target_faces:
        return
    face_id = getattr(main_window, 'hovered_input_face_id', None)
    for target_face in main_window.target_faces.values():
        target_face.set_highlighted(bool(face_id) and face_id in target_face.assigned_input_faces)

def refresh_input_faces_usage_markers(main_window: 'MainWindow'):
    """Colour the border of every input face with the colour of the target face using it.

    An input face that is not assigned to any target face gets no border.
    """
    refresh_target_face_colors(main_window)
    refresh_target_face_highlights(main_window)

    if not main_window.input_faces:
        return

    target_faces = list(main_window.target_faces.values())
    current_target_face = getattr(main_window, 'cur_selected_target_face_button', False)
    # The target face being edited wins: an input face assigned to several target
    # faces is shown in the colour of the one that is currently selected.
    if current_target_face and current_target_face in target_faces:
        target_faces.remove(current_target_face)
        target_faces.insert(0, current_target_face)

    owner_colors: Dict[str, str] = {}
    for target_face in target_faces:
        color = getattr(target_face, 'color', None)
        if not color:
            continue
        for input_face_id in target_face.assigned_input_faces:
            owner_colors.setdefault(input_face_id, color)

    for input_face_id, input_face_button in main_window.input_faces.items():
        input_face_button.set_usage_color(owner_colors.get(input_face_id))

def uncheck_all_merged_embeddings(main_window: 'MainWindow'):
    for _, embed_button in  main_window.merged_embeddings.items():
        embed_button.setChecked(False)

def find_target_faces(main_window: 'MainWindow'):
    control = main_window.control.copy()
    video_processor = main_window.video_processor
    if video_processor.media_path:
        frame = None
        media_capture = video_processor.media_capture

        if video_processor.file_type=='image':
            frame = misc_helpers.read_image_file(video_processor.media_path)
        elif video_processor.file_type=='video' and media_capture:
            ret,frame = misc_helpers.read_frame(media_capture)
            media_capture.set(cv2.CAP_PROP_POS_FRAMES, video_processor.current_frame_number)
        elif video_processor.file_type=='webcam' and media_capture:
            ret, frame = misc_helpers.read_frame(media_capture)
            media_capture.set(cv2.CAP_PROP_POS_FRAMES, video_processor.current_frame_number)

        if frame is not None:
        # Frame must be in RGB format
            # Swap the channels from BGR to RGB（转为连续数组：[...,::-1] 是负步长视图，
            # torch.from_numpy 不支持，且下游投影转换器直接消费该数组）
            frame = numpy.ascontiguousarray(frame[..., ::-1])

            # print(frame)
            img = torch.from_numpy(frame.astype('uint8')).to(main_window.models_processor.device)
            img = img.permute(2,0,1)
            vr180_mode = bool(control.get('VR180ModeEnableToggle', False))
            # VR180 模式下不做手动旋转：VR 管线按原始全景坐标取投影，需保持坐标系一致
            if control['ManualRotationEnableToggle'] and not vr180_mode:
                img = v2.functional.rotate(img, angle=control['ManualRotationAngleSlider'], interpolation=v2.InterpolationMode.BILINEAR, expand=True)

            bboxes, kpss_5, _ = main_window.models_processor.run_detect(img, control['DetectorModelSelection'], max_num=control['MaxFacesToDetectSlider'], score=control['DetectorScoreSlider']/100.0, input_size=(512, 512), use_landmark_detection=control['LandmarkDetectToggle'], landmark_detect_mode=control['LandmarkDetectModelSelection'], landmark_score=control["LandmarkDetectScoreSlider"]/100.0, from_points=control["DetectFromPointsToggle"], rotation_angles=[0] if not control["AutoRotationToggle"] else [0, 90, 180, 270])

            # VR180 模式：目标脸的 embedding 必须与 VR 处理管线的匹配端同域，
            # 即从投影校正后的透视 crop 提取，而不是从柱面畸变的全景图提取。
            equirect_converter = None
            if vr180_mode:
                from app.helpers.vr_utils import EquirectangularConverter
                equirect_converter = EquirectangularConverter(frame, device=main_window.models_processor.device)

            ret = []
            for i, face_kps in enumerate(kpss_5):
                recognize_img, recognize_kps = img, face_kps
                if equirect_converter is not None:
                    bbox_single = bboxes[i]
                    theta, phi = equirect_converter.calculate_theta_phi_from_bbox(bbox_single)
                    # 动态 FOV 计算与 FrameWorker 的 VR 管线保持一致，保证 crop 同域
                    angular_width_deg = (bbox_single[2] - bbox_single[0]) / equirect_converter.width * 360.0
                    angular_height_deg = (bbox_single[3] - bbox_single[1]) / equirect_converter.height * 180.0
                    dynamic_fov = float(numpy.clip(max(angular_width_deg, angular_height_deg) * 1.15, 15.0, 100.0))
                    face_crop_tensor = equirect_converter.get_perspective_crop(
                        FOV=dynamic_fov, THETA=theta, PHI=phi, height=512, width=512
                    )
                    if face_crop_tensor is not None and face_crop_tensor.numel() > 0:
                        _, kps_on_crop_list, _ = main_window.models_processor.run_detect(
                            face_crop_tensor, control['DetectorModelSelection'], max_num=1,
                            score=control['DetectorScoreSlider']/100.0,
                            input_size=(512, 512),
                            use_landmark_detection=control['LandmarkDetectToggle'],
                            landmark_detect_mode=control['LandmarkDetectModelSelection'],
                            landmark_score=control["LandmarkDetectScoreSlider"]/100.0,
                            from_points=control["DetectFromPointsToggle"], rotation_angles=[0]
                        )
                        has_kps = kps_on_crop_list.any() if isinstance(kps_on_crop_list, numpy.ndarray) else bool(kps_on_crop_list)
                        if has_kps:
                            recognize_img, recognize_kps = face_crop_tensor, kps_on_crop_list[0]
                        else:
                            print(f"查找面部(VR180): 投影 crop 内未检出关键点，回退使用全景 embedding（theta={theta:.1f}, phi={phi:.1f}）")
                face_emb, cropped_img = main_window.models_processor.run_recognize_direct(recognize_img, recognize_kps, control['SimilarityTypeSelection'], control['RecognitionModelSelection'])
                ret.append([recognize_kps, face_emb, cropped_img, recognize_img])

            if ret:
                # Loop through all faces in video frame
                for face in ret:
                    found = False
                    # Check if this face has already been found
                    for face_id, target_face in main_window.target_faces.items():
                        parameters = main_window.parameters[target_face.face_id]
                        threshhold = parameters['SimilarityThresholdSlider']
                        if main_window.models_processor.findCosineDistance(target_face.get_embedding(control['RecognitionModelSelection']), face[1]) >= threshhold:
                            found = True
                            break
                    if not found:
                        face_img = face[2].cpu().numpy()
                        face_img = face_img[..., ::-1]  # Swap the channels from RGB to BGR
                        face_img = numpy.ascontiguousarray(face_img)
                        # crop = cv2.resize(face[2].cpu().numpy(), (82, 82))
                        pixmap = common_widget_actions.get_pixmap_from_frame(main_window, face_img)

                        embedding_store: Dict[str, numpy.ndarray] = {}
                        # Ottenere i valori di 'options'
                        options = SETTINGS_LAYOUT_DATA['Face Recognition']['RecognitionModelSelection']['options']
                        for option in options:
                            if option != control['RecognitionModelSelection']:
                                target_emb, _ = main_window.models_processor.run_recognize_direct(face[3], face[0], control['SimilarityTypeSelection'], option)
                                embedding_store[option] = target_emb
                            else:
                                embedding_store[control['RecognitionModelSelection']] = face[1]

                        face_id = str(uuid.uuid1().int)

                        list_view_actions.add_media_thumbnail_to_target_faces_list(main_window, face_img, embedding_store, pixmap, face_id)
            # Select the first target face if no target face is already selected
        if main_window.target_faces and not main_window.selected_target_face_id:
            list(main_window.target_faces.values())[0].click()

    if main_window.video_processor.processing:
        main_window.video_processor.stop_processing()
    common_widget_actions.refresh_frame(main_window)

    common_widget_actions.update_gpu_memory_progressbar(main_window)