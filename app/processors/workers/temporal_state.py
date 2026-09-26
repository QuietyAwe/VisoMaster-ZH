import threading
import time
from typing import Dict, List, Optional

import numpy as np

from app.processors.utils.one_euro_filter import OneEuroFilterSet

# Temporal stabilisation layer.
#
# The frame pipeline in this project is stateless: every frame is detected,
# recognised and thresholded on its own, so a similarity value hovering around
# the threshold makes the swap blink on and off. This module keeps a small
# amount of state between frames:
#
#   * face slots are re-attached across frames with a greedy IoU match,
#   * the similarity of every slot/target pair is smoothed with an EMA,
#   * a locked face only needs the (lower) hold threshold to stay locked,
#   * the keypoints of every slot are smoothed with a 1 Euro filter.
#
# FrameWorker instances are created per frame and run in parallel, so the state
# must live outside of them. `commit()` serialises only the (cheap) state
# update and keeps it ordered by sequence number, while detection and
# recognition stay parallel.

class FaceSlotState:
    """Cross frame state of a single tracked face."""

    def __init__(self, slot_id: int):
        self.slot_id: int = slot_id
        self.bbox: np.ndarray = np.zeros(4, dtype=np.float64)
        self.locked: bool = False
        self.bound_target_face_id: Optional[str] = None
        self.sim_ema: Dict[str, float] = {}
        self.missed_count: int = 0
        self.kps5_filter: Optional[OneEuroFilterSet] = None
        self.kps_all_filter: Optional[OneEuroFilterSet] = None

    def reset_filters(self):
        self.kps5_filter = None
        self.kps_all_filter = None


def bbox_iou(bbox_a: np.ndarray, bbox_b: np.ndarray) -> float:
    """IoU of two [x_min, y_min, x_max, y_max] boxes."""
    a = np.asarray(bbox_a, dtype=np.float64).ravel()[:4]
    b = np.asarray(bbox_b, dtype=np.float64).ravel()[:4]
    if a.size < 4 or b.size < 4:
        return 0.0

    inter_x1 = max(a[0], b[0])
    inter_y1 = max(a[1], b[1])
    inter_x2 = min(a[2], b[2])
    inter_y2 = min(a[3], b[3])

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0.0:
        return 0.0

    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter_area
    if union <= 0.0:
        return 0.0
    return float(inter_area / union)


class TemporalStateManager:
    """Thread safe, sequence ordered temporal state for the frame pipeline."""

    def __init__(self, iou_threshold: float = 0.3, timeout: float = 2.0, default_freq: float = 30.0,
                 max_lead: int = 8):
        self.iou_threshold = float(iou_threshold)
        self.timeout = float(timeout)
        self.default_freq = float(default_freq)
        # How far ahead of the expected sequence a frame may be before the state is
        # considered stale (frames in flight are at most `num_threads`).
        self.max_lead = int(max_lead)

        self._cv = threading.Condition(threading.Lock())
        self.slots: Dict[int, FaceSlotState] = {}
        self._next_slot_id = 0
        self.expected_sequence: Optional[int] = None
        self.last_committed_sequence: Optional[int] = None

    # ------------------------------------------------------------------ public

    def reset(self, expected_sequence: Optional[int] = None):
        """Drop every tracked face. Called on seek, stop, media change, ..."""
        with self._cv:
            self.slots.clear()
            self._next_slot_id = 0
            self.expected_sequence = expected_sequence
            self.last_committed_sequence = None
            self._cv.notify_all()

    def commit(self, sequence: int, detections: List[dict], thresholds: Dict[str, float],
               hysteresis: Optional[Dict[str, float]] = None, smoothing: Optional[Dict[str, float]] = None,
               freq: float = 30.0, max_missed: int = 2, keypoint_smoothing: bool = True,
               min_cutoff: float = 1.0, beta: float = 0.01) -> List[dict]:
        """Advance the temporal state by one frame and return one decision per detection.

        `detections` is a list of dicts with the keys 'bbox', 'kps_5', 'kps_all' and
        'sims' ({target_face_id: similarity in the 0..100 scale}).
        The returned list has the same length and order and each entry contains
        'slot_id', 'matches' (ordered list of (target_face_id, similarity)),
        'kps_5' and 'kps_all'.
        """
        hysteresis = hysteresis or {}
        smoothing = smoothing or {}

        with self._cv:
            if self.expected_sequence is None:
                self.expected_sequence = sequence

            # A frame that was already passed (duplicate / stale worker) cannot
            # move the state forward, fall back to the stateless decision.
            if sequence < self.expected_sequence:
                return self._passthrough(detections, thresholds)

            if sequence - self.expected_sequence > self.max_lead:
                # Far ahead of the state: a whole section of frames was skipped
                # (seek, stop, swap turned off, ...), do not wait for them.
                self.slots.clear()
                self._next_slot_id = 0
                self.expected_sequence = sequence

            deadline = time.monotonic() + self.timeout
            while self.expected_sequence < sequence:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    # The previous frame never committed (dropped / stopped):
                    # resynchronise instead of blocking forever.
                    print(f"TemporalStateManager: timeout waiting for sequence {self.expected_sequence}, resyncing at {sequence}")
                    self.slots.clear()
                    self._next_slot_id = 0
                    self.expected_sequence = sequence
                    break
                self._cv.wait(remaining)
                if self.expected_sequence is None:
                    self.expected_sequence = sequence

            if self.expected_sequence > sequence:
                return self._passthrough(detections, thresholds)

            decisions = self._advance(sequence, detections, thresholds, hysteresis, smoothing,
                                      freq, max_missed, keypoint_smoothing, min_cutoff, beta)
            self.expected_sequence = sequence + 1
            self.last_committed_sequence = sequence
            self._cv.notify_all()
            return decisions

    # ----------------------------------------------------------------- private

    def _passthrough(self, detections: List[dict], thresholds: Dict[str, float]) -> List[dict]:
        decisions = []
        for det in detections:
            matches = [(face_id, float(sim)) for face_id, sim in (det.get('sims') or {}).items()
                       if float(sim) >= float(thresholds.get(face_id, 60.0))]
            matches.sort(key=lambda item: item[1], reverse=True)
            decisions.append({
                'slot_id': None,
                'matches': matches,
                'kps_5': det.get('kps_5'),
                'kps_all': det.get('kps_all'),
            })
        return decisions

    def _advance(self, sequence: int, detections: List[dict], thresholds: Dict[str, float],
                 hysteresis: Dict[str, float], smoothing: Dict[str, float], freq: float,
                 max_missed: int, keypoint_smoothing: bool, min_cutoff: float, beta: float) -> List[dict]:
        freq = float(freq) if freq and freq > 0 else self.default_freq
        timestamp = sequence / freq

        detection_count = len(detections)
        slot_ids: List[Optional[int]] = [None] * detection_count

        if self.slots and detection_count:
            pairs = []
            for slot_id, slot in self.slots.items():
                for det_index in range(detection_count):
                    iou = bbox_iou(slot.bbox, detections[det_index].get('bbox'))
                    if iou >= self.iou_threshold:
                        pairs.append((iou, slot_id, det_index))
            pairs.sort(key=lambda pair: pair[0], reverse=True)

            matched_slots = set()
            matched_detections = set()
            for _iou, slot_id, det_index in pairs:
                if slot_id in matched_slots or det_index in matched_detections:
                    continue
                matched_slots.add(slot_id)
                matched_detections.add(det_index)
                slot_ids[det_index] = slot_id
        else:
            matched_slots = set()

        # Age and drop the slots that were not seen in this frame.
        for slot_id in list(self.slots.keys()):
            if slot_id not in matched_slots:
                slot = self.slots[slot_id]
                slot.missed_count += 1
                if slot.missed_count > max_missed:
                    del self.slots[slot_id]

        decisions = []
        for det_index, det in enumerate(detections):
            slot_id = slot_ids[det_index]
            if slot_id is None or slot_id not in self.slots:
                slot = FaceSlotState(self._next_slot_id)
                self._next_slot_id += 1
                self.slots[slot.slot_id] = slot
            else:
                slot = self.slots[slot_id]
                if slot.missed_count > 0:
                    # The face was missing for at least one frame: restart the
                    # filters so the smoothed keypoints do not slide over from
                    # the old position.
                    slot.reset_filters()

            slot.missed_count = 0
            bbox = det.get('bbox')
            if bbox is not None:
                slot.bbox = np.asarray(bbox, dtype=np.float64).ravel()[:4].copy()

            sims = {face_id: float(sim) for face_id, sim in (det.get('sims') or {}).items()}
            self._update_similarity_ema(slot, sims, smoothing)
            matches = self._arbitrate(slot, sims, thresholds, hysteresis)

            kps_5 = det.get('kps_5')
            kps_all = det.get('kps_all')
            if keypoint_smoothing:
                kps_5 = self._filter_keypoints(slot, 'kps5_filter', kps_5, timestamp, freq, min_cutoff, beta)
                kps_all = self._filter_keypoints(slot, 'kps_all_filter', kps_all, timestamp, freq, min_cutoff, beta)
            else:
                slot.reset_filters()

            decisions.append({
                'slot_id': slot.slot_id,
                'matches': matches,
                'kps_5': kps_5,
                'kps_all': kps_all,
            })

        return decisions

    def _update_similarity_ema(self, slot: FaceSlotState, sims: Dict[str, float], smoothing: Dict[str, float]):
        updated = {}
        for face_id, sim in sims.items():
            alpha = float(smoothing.get(face_id, 0.5))
            previous = slot.sim_ema.get(face_id)
            if previous is None or alpha <= 0.0:
                updated[face_id] = sim
            else:
                updated[face_id] = alpha * sim + (1.0 - alpha) * previous
        slot.sim_ema = updated

    def _arbitrate(self, slot: FaceSlotState, sims: Dict[str, float], thresholds: Dict[str, float],
                   hysteresis: Dict[str, float]) -> List[tuple]:
        """Pick the target face of this slot using the smoothed similarity and hysteresis."""
        best_face_id, best_sim = None, None
        sticky_face_id, sticky_sim = None, None

        for face_id, sim in slot.sim_ema.items():
            threshold = float(thresholds.get(face_id, 60.0))
            if slot.locked and slot.bound_target_face_id == face_id:
                # Already locked: a lower threshold is enough to stay locked.
                threshold = max(threshold - float(hysteresis.get(face_id, 0.0)), 1.0)

            if sim >= threshold:
                if best_sim is None or sim > best_sim:
                    best_sim, best_face_id = sim, face_id
                if face_id == slot.bound_target_face_id:
                    sticky_sim, sticky_face_id = sim, face_id

        if sticky_face_id is not None:
            chosen_face_id, chosen_sim = sticky_face_id, sticky_sim
        else:
            chosen_face_id, chosen_sim = best_face_id, best_sim

        if chosen_face_id is not None:
            slot.locked = True
            slot.bound_target_face_id = chosen_face_id
            return [(chosen_face_id, float(chosen_sim))]

        slot.locked = False
        slot.bound_target_face_id = None
        return []

    def _filter_keypoints(self, slot: FaceSlotState, filter_attribute: str, keypoints,
                          timestamp: float, freq: float, min_cutoff: float, beta: float):
        if keypoints is None:
            return None
        keypoints = np.asarray(keypoints)
        if keypoints.dtype == object:
            # The landmark detectors return an object array, a single element is
            # the (num_points, 2) array of one face.
            if keypoints.size != 1:
                return keypoints
            keypoints = np.asarray(keypoints[0])
        if keypoints.ndim != 2 or keypoints.shape[-1] != 2 or keypoints.size == 0:
            return keypoints

        keypoint_filter = getattr(slot, filter_attribute)
        if keypoint_filter is None:
            keypoint_filter = OneEuroFilterSet(freq=freq, min_cutoff=min_cutoff, beta=beta)
            setattr(slot, filter_attribute, keypoint_filter)
        else:
            keypoint_filter.freq = freq
            keypoint_filter.min_cutoff = min_cutoff
            keypoint_filter.beta = beta

        return keypoint_filter.filter(keypoints, timestamp)
