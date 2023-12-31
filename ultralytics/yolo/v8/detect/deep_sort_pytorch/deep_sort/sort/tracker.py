from __future__ import absolute_import
import numpy as np
from . import kalman_filter
from . import linear_assignment
from . import iou_matching
from .track import Track
from sklearn.cluster import DBSCAN


class Tracker:
    

    def __init__(self, metric, max_iou_distance=0.7, max_age=100, n_init=3):
        self.metric = metric
        self.max_iou_distance = max_iou_distance
        self.max_age = max_age
        self.n_init = n_init

        self.kf = kalman_filter.KalmanFilter()
        self.tracks = []
        self._next_id = 1

        self.unmatched_tracks_features = []

    def predict(self):

        for track in self.tracks:
            track.predict(self.kf)

    def increment_ages(self):
        for track in self.tracks:
            track.increment_age()
            track.mark_missed()

    def update(self, detections):

        # Run matching cascade.
        matches, unmatched_tracks, unmatched_detections = self._match(detections)
''' ********************************************************************************************
    ********************************************************************************************
'''
        if all_features:
          X = np.array(all_features).reshape(-1, 1)
          cluster = DBSCAN(eps=0.5, min_samples=4, metric='euclidean', n_jobs=8).fit(X)
          labels = cluster.labels_
          print('标签长度', len(labels))


        # Update track set.
        '''匹配上的'''
        for track_idx, detection_idx in matches:
            self.tracks[track_idx].update(self.kf, detections[detection_idx])
        '''未匹配上的轨迹'''
        for track_idx in unmatched_tracks:
            self.tracks[track_idx].mark_missed()
        '''未匹配上的检测框---分配新轨迹'''
        for detection_idx in unmatched_detections:
            self._initiate_track(detections[detection_idx])

        self.tracks = [t for t in self.tracks if not t.is_deleted()]

        # Update distance metric.
        active_targets = [t.track_id for t in self.tracks if t.is_confirmed()]
        features, targets = [], []
        for track in self.tracks:
            if not track.is_confirmed():
                continue
            features += track.features
            targets += [track.track_id for _ in track.features]
            track.features = []
        self.metric.partial_fit(
            np.asarray(features), np.asarray(targets), active_targets)

    def _match(self, detections):

        def gated_metric(tracks, dets, track_indices, detection_indices):
            features = np.array([dets[i].feature for i in detection_indices])
            targets = np.array([tracks[i].track_id for i in track_indices])
            cost_matrix = self.metric.distance(features, targets)
            cost_matrix = linear_assignment.gate_cost_matrix(
                self.kf, cost_matrix, tracks, dets, track_indices, detection_indices)

            return cost_matrix

        # Split track set into confirmed and unconfirmed tracks.
        confirmed_tracks = [
            i for i, t in enumerate(self.tracks) if t.is_confirmed()]
        unconfirmed_tracks = [
            i for i, t in enumerate(self.tracks) if not t.is_confirmed()]

        # Associate confirmed tracks using appearance features.
        '''
            级联匹配的三种状态
        '''
        matches_a, unmatched_tracks_a, unmatched_detections = \
            linear_assignment.matching_cascade(gated_metric, self.metric.matching_threshold,
                                               self.max_age, self.tracks, detections, confirmed_tracks)

        '''
            ******* IOU 匹配 ********
        '''
        # Associate remaining tracks together with unconfirmed tracks using IOU.
        iou_track_candidates = unconfirmed_tracks + [k for k in unmatched_tracks_a if self.tracks[k].time_since_update == 1]

        unmatched_tracks_a = [k for k in unmatched_tracks_a if self.tracks[k].time_since_update != 1]

        matches_b, unmatched_tracks_b, unmatched_detections = linear_assignment.min_cost_matching(
                iou_matching.iou_cost, self.max_iou_distance, self.tracks,
                detections, iou_track_candidates, unmatched_detections)
        '''
            IOU 匹配后的三种状态
            unmatched_tracks 是 list 类型
        '''
        matches = matches_a + matches_b

        unmatched_tracks = list(set(unmatched_tracks_a + unmatched_tracks_b))
        return matches, unmatched_tracks, unmatched_detections

    def _initiate_track(self, detection):
        mean, covariance = self.kf.initiate(detection.to_xyah())
        '''
            
        '''
        self.tracks.append(Track(mean, covariance, self._next_id, self.n_init,
                                 self.max_age, detection.oid, detection.feature))
        self._next_id += 1

