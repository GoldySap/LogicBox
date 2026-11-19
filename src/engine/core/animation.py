import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class AnimationKeyframe:
    time: float
    value: object


@dataclass
class AnimationClip:
    name: str
    duration: float
    tracks: Dict[str, List[AnimationKeyframe]] = field(default_factory=dict)
    looping: bool = False

    def validate(self):
        if self.duration < 0:
            raise ValueError("duration cannot be negative")
        for track in self.tracks.values():
            times = [keyframe.time for keyframe in track]
            if times != sorted(times):
                raise ValueError("keyframes must be ordered by time")
            if times and (times[0] < 0 or times[-1] > self.duration):
                raise ValueError("keyframe outside clip duration")

    def sample(self, track_name: str, time: float):
        track = self.tracks.get(track_name)
        if not track:
            return None
        time = min(max(time, 0.0), self.duration)
        if time <= track[0].time:
            return track[0].value
        if time >= track[-1].time:
            return track[-1].value
        for left, right in zip(track, track[1:]):
            if left.time <= time <= right.time:
                span = right.time - left.time
                if span == 0:
                    return right.value
                factor = (time - left.time) / span
                if isinstance(left.value, (int, float)) and isinstance(right.value, (int, float)):
                    return left.value + (right.value - left.value) * factor
                return right.value
        return track[-1].value


class AnimationStateMachine:
    def __init__(self):
        self.states: Dict[str, AnimationClip] = {}
        self.transitions: Dict[tuple, object] = {}
        self.current: Optional[str] = None

    def add_state(self, name: str, clip: AnimationClip):
        clip.validate()
        self.states[name] = clip
        if self.current is None:
            self.current = name

    def add_transition(self, source: str, target: str, condition):
        self.transitions[(source, target)] = condition

    def update(self, time: float, context):
        if self.current is None:
            return None
        for (source, target), condition in self.transitions.items():
            if source == self.current and bool(condition(context)):
                self.current = target
                break
        clip = self.states[self.current]
        elapsed = time
        if clip.looping:
            elapsed %= clip.duration if clip.duration else 1.0
        return {
            name: clip.sample(name, elapsed)
            for name in clip.tracks
        }
