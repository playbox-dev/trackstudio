"""
BEV Cluster Merger

This module implements cross-camera tracking using bird's eye view clustering
and appearance-based features for associating tracks across multiple cameras.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..models.reid_extractor import TorchReIDExtractor
from ..trackers.base import BEVTrack
from ..vision_config import CrossCameraConfig
from .base import VisionMerger

logger = logging.getLogger(__name__)


@dataclass
class GlobalTrack:
    """
    Represents a global track that may span multiple cameras.

    This class maintains the state of a track across multiple camera views,
    including position history, appearance features, and camera associations.

    Attributes:
        global_id: Unique identifier for this global track
        camera_tracks: Mapping from camera_id to local track_id
        last_seen: Timestamp when this track was last updated
        positions: History of (x, y, timestamp) positions
        appearance_features: Averaged appearance features across cameras
        smoothed_position: Current smoothed position estimate
        velocity: Current velocity estimate (vx, vy)
    """

    global_id: str
    camera_tracks: dict[int, str]  # camera_id -> local_track_id
    last_seen: float
    positions: list[tuple[float, float, float]]  # (x, y, timestamp)
    appearance_features: np.ndarray | None = None
    smoothed_position: tuple[float, float] | None = None
    velocity: tuple[float, float] = (0.0, 0.0)


@dataclass
class TrackCandidate:
    """
    Represents a track candidate for clustering.

    A temporary representation of a track used during the clustering
    process to determine which tracks should be merged.

    Attributes:
        camera_id: ID of the source camera
        local_track_id: Local track ID within the camera
        position: Current position in BEV coordinates
        appearance_features: Optional appearance features for matching
        original_bev_track: Original BEV track object
    """

    camera_id: int
    local_track_id: str
    position: tuple[float, float]
    appearance_features: np.ndarray | None
    original_bev_track: BEVTrack


class BEVClusterMerger(VisionMerger):
    """
    Cross-camera merger that uses BEV clustering and appearance features.

    This merger associates tracks from different cameras by clustering them
    in bird's eye view space and using appearance features for validation.
    It maintains global track identities across camera boundaries.

    Attributes:
        config: Configuration for clustering parameters
        reid_extractor: Optional ReID feature extractor
        global_tracks: Dictionary of active global tracks
        next_global_id: Counter for generating new global IDs
        track_id_mapping: Mapping from (camera_id, local_id) to global_id
        total_tracks_created: Total number of global tracks created
        multi_camera_associations: Number of successful cross-camera associations
    """

    def __init__(self, config: CrossCameraConfig, reid_extractor: TorchReIDExtractor | None = None) -> None:
        """
        Initialize the BEV cluster merger.

        Args:
            config: Configuration object with clustering parameters
            reid_extractor: Optional ReID feature extractor for appearance matching
        """
        super().__init__()
        self.config = config
        self.reid_extractor = reid_extractor

        self.global_tracks: dict[str, GlobalTrack] = {}
        self.next_global_id = 1
        self.track_id_mapping: dict[tuple[int, str], str] = {}
        self.total_tracks_created = 0
        self.multi_camera_associations = 0

    def merge(
        self,
        bev_tracks: list[BEVTrack],
        timestamp: float,
        stream_frames: dict[int, np.ndarray] | None = None,
        reid_features: dict[str, np.ndarray] | None = None,
    ) -> list[BEVTrack]:
        """
        Merge BEV tracks from multiple cameras using clustering.

        This method clusters tracks from different cameras based on spatial
        proximity and appearance similarity, assigning global IDs to maintain
        track identity across camera boundaries.

        Args:
            bev_tracks: List of tracks in bird's eye view coordinates
            timestamp: Current timestamp for track aging
            stream_frames: Optional camera frames (for compatibility)
            reid_features: Optional ReID features for appearance matching

        Returns:
            List of BEV tracks with global IDs assigned
        """
        # Use empty dict if None provided for compatibility
        if reid_features is None:
            reid_features = {}

        self._cleanup_old_tracks(timestamp)

        track_candidates: list[TrackCandidate] = []
        for bev_track in bev_tracks:
            candidate = TrackCandidate(
                camera_id=bev_track.camera_id,
                local_track_id=str(bev_track.track_id),
                position=(bev_track.bev_x, bev_track.bev_y),
                appearance_features=reid_features.get(str(bev_track.track_id)),
                original_bev_track=bev_track,
            )
            track_candidates.append(candidate)

        clusters = self._cluster_tracks(track_candidates)
        return self._assign_global_ids_to_clusters(clusters, timestamp)

    def _cluster_tracks(self, candidates: list[TrackCandidate]) -> list[list[TrackCandidate]]:
        """
        Cluster track candidates based on spatial and appearance similarity.

        Creates clusters of tracks that likely represent the same object
        across different cameras using spatial distance and appearance features.

        Args:
            candidates: List of track candidates to cluster

        Returns:
            List of clusters, where each cluster is a list of candidates
        """
        if not candidates:
            return []

        n = len(candidates)
        adj_matrix = np.zeros((n, n), dtype=bool)

        # Build adjacency matrix based on similarity
        for i in range(n):
            for j in range(i + 1, n):
                # Don't cluster tracks from the same camera
                if candidates[i].camera_id == candidates[j].camera_id:
                    continue

                # Check spatial distance
                spatial_dist = np.linalg.norm(np.array(candidates[i].position) - np.array(candidates[j].position))
                if spatial_dist > self.config.spatial_threshold:
                    continue

                # Check appearance similarity if features available
                feat_i = candidates[i].appearance_features
                feat_j = candidates[j].appearance_features
                if feat_i is not None and feat_j is not None:
                    cosine_sim = np.dot(feat_i, feat_j) / (np.linalg.norm(feat_i) * np.linalg.norm(feat_j) + 1e-8)
                    appearance_dist = 1.0 - cosine_sim
                    if appearance_dist > self.config.appearance_threshold:
                        continue

                # Mark as connected if all criteria met
                adj_matrix[i, j] = adj_matrix[j, i] = True

        # Find connected components using DFS
        visited = [False] * n
        clusters: list[list[TrackCandidate]] = []
        for i in range(n):
            if not visited[i]:
                cluster: list[TrackCandidate] = []
                self._dfs(i, adj_matrix, visited, cluster, candidates)
                clusters.append(cluster)

        return clusters

    def _dfs(
        self,
        u: int,
        adj: np.ndarray,
        visited: list[bool],
        cluster: list[TrackCandidate],
        candidates: list[TrackCandidate],
    ) -> None:
        """
        Depth-first search to find connected components in the track graph.

        Args:
            u: Current node index
            adj: Adjacency matrix
            visited: List of visited flags
            cluster: Current cluster being built
            candidates: List of all track candidates
        """
        visited[u] = True
        cluster.append(candidates[u])
        for v in range(len(candidates)):
            if adj[u, v] and not visited[v]:
                self._dfs(v, adj, visited, cluster, candidates)

    def _assign_global_ids_to_clusters(self, clusters: list[list[TrackCandidate]], timestamp: float) -> list[BEVTrack]:
        """
        Assign global IDs to clustered tracks.

        For each cluster, either assigns an existing global ID or creates
        a new one, maintaining track continuity across frames.

        Args:
            clusters: List of track clusters
            timestamp: Current timestamp

        Returns:
            List of BEV tracks with global IDs assigned
        """
        updated_tracks: list[BEVTrack] = []

        for cluster in clusters:
            if len(cluster) == 1:
                # Single track - check if it's already in a global track
                candidate = cluster[0]
                key = (candidate.camera_id, candidate.local_track_id)

                if key in self.track_id_mapping:
                    global_id = self.track_id_mapping[key]
                    if global_id in self.global_tracks:
                        self.global_tracks[global_id].last_seen = timestamp
                        self.global_tracks[global_id].positions.append(
                            (candidate.position[0], candidate.position[1], timestamp)
                        )
                else:
                    global_id = self._create_new_global_track_for_cluster(cluster, timestamp)
                    self.track_id_mapping[key] = global_id

                # Create updated BEV track
                updated_track = candidate.original_bev_track
                updated_track.global_id = int(global_id)
                updated_tracks.append(updated_track)

            else:
                # Multi-camera cluster - merge or create new global track
                existing_global_ids: set[str] = set()
                for candidate in cluster:
                    key = (candidate.camera_id, candidate.local_track_id)
                    if key in self.track_id_mapping:
                        existing_global_ids.add(self.track_id_mapping[key])

                if existing_global_ids:
                    # Merge with existing tracks
                    primary_id = self._merge_global_tracks(existing_global_ids, timestamp)
                    self.multi_camera_associations += 1
                else:
                    # Create new global track
                    primary_id = self._create_new_global_track_for_cluster(cluster, timestamp)

                # Update all candidates with the same global ID
                for candidate in cluster:
                    key = (candidate.camera_id, candidate.local_track_id)
                    self.track_id_mapping[key] = primary_id

                    updated_track = candidate.original_bev_track
                    updated_track.global_id = int(primary_id)
                    updated_tracks.append(updated_track)

        return updated_tracks

    def _create_new_global_track_for_cluster(self, cluster: list[TrackCandidate], timestamp: float) -> str:
        """
        Create a new global track for a cluster of candidates.

        Args:
            cluster: List of track candidates to merge into a global track
            timestamp: Current timestamp

        Returns:
            Global ID of the newly created track
        """
        global_id = str(self.next_global_id)
        self.next_global_id += 1

        # Calculate average position
        avg_x = float(np.mean([c.position[0] for c in cluster]))
        avg_y = float(np.mean([c.position[1] for c in cluster]))

        # Average appearance features if available
        features = [c.appearance_features for c in cluster if c.appearance_features is not None]
        avg_features = np.mean(features, axis=0) if features else None

        self.global_tracks[global_id] = GlobalTrack(
            global_id=global_id,
            camera_tracks={c.camera_id: c.local_track_id for c in cluster},
            last_seen=timestamp,
            positions=[(avg_x, avg_y, timestamp)],
            appearance_features=avg_features,
        )
        self.total_tracks_created += 1
        return global_id

    def _merge_global_tracks(self, global_ids: set[str], timestamp: float) -> str:
        """
        Merge multiple global tracks into one.

        Args:
            global_ids: Set of global IDs to merge
            timestamp: Current timestamp

        Returns:
            Primary global ID after merging
        """
        primary_id = min(global_ids, key=int)
        primary_track = self.global_tracks[primary_id]

        for gid in global_ids:
            if gid != primary_id and gid in self.global_tracks:
                other_track = self.global_tracks[gid]
                primary_track.camera_tracks.update(other_track.camera_tracks)
                primary_track.positions.extend(other_track.positions)

                # Merge appearance features
                if other_track.appearance_features is not None:
                    if primary_track.appearance_features is None:
                        primary_track.appearance_features = other_track.appearance_features
                    else:
                        primary_track.appearance_features = (
                            primary_track.appearance_features + other_track.appearance_features
                        ) / 2.0

                # Update track mappings
                for cam_id, track_id in other_track.camera_tracks.items():
                    self.track_id_mapping[(cam_id, track_id)] = primary_id

                del self.global_tracks[gid]

        # Sort positions by timestamp and update last seen
        primary_track.positions.sort(key=lambda p: p[2])
        primary_track.last_seen = timestamp
        return primary_id

    def _cleanup_old_tracks(self, current_timestamp: float) -> None:
        """
        Remove expired global tracks based on age.

        Args:
            current_timestamp: Current timestamp for age calculation
        """
        expired_ids: list[str] = []
        for global_id, track in self.global_tracks.items():
            age_seconds = current_timestamp - track.last_seen
            if age_seconds > self.config.max_track_age_s:
                expired_ids.append(global_id)

                # Remove from mapping
                for cam_id, local_id in track.camera_tracks.items():
                    key = (cam_id, local_id)
                    if key in self.track_id_mapping:
                        del self.track_id_mapping[key]

        for global_id in expired_ids:
            del self.global_tracks[global_id]

        if expired_ids:
            logger.debug(f"🧹 Cleaned up {len(expired_ids)} expired global tracks")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the cross-camera merging process.

        Returns:
            Dictionary containing merger statistics and performance metrics
        """
        return {
            "merger_type": "BEV Cluster",
            "total_global_tracks": len(self.global_tracks),
            "total_tracks_created": self.total_tracks_created,
            "multi_camera_associations": self.multi_camera_associations,
            "active_track_mappings": len(self.track_id_mapping),
        }
