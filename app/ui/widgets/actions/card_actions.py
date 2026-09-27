
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
            frame = frame[..., ::-1]  # Swap the channels from BGR to RGB

            # print(frame)
            img = torch.from_numpy(frame.astype('uint8')).to(main_window.models_processor.device)
            img = img.permute(2,0,1)
            if control['ManualRotationEnableToggle']:
                img = v2.functional.rotate(img, angle=control['ManualRotationAngleSlider'], interpolation=v2.InterpolationMode.BILINEAR, expand=True)

            _, kpss_5, _ = main_window.models_processor.run_detect(img, control['DetectorModelSelection'], max_num=control['MaxFacesToDetectSlider'], score=control['DetectorScoreSlider']/100.0, input_size=(512, 512), use_landmark_detection=control['LandmarkDetectToggle'], landmark_detect_mode=control['LandmarkDetectModelSelection'], landmark_score=control["LandmarkDetectScoreSlider"]/100.0, from_points=control["DetectFromPointsToggle"], rotation_angles=[0] if not control["AutoRotationToggle"] else [0, 90, 180, 270])

            ret = []
            for face_kps in kpss_5:
                face_emb, cropped_img = main_window.models_processor.run_recognize_direct(img, face_kps, control['SimilarityTypeSelection'], control['RecognitionModelSelection'])
                ret.append([face_kps, face_emb, cropped_img, img])

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