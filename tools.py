from common import PrassError
import bisect
import math


def parse_scxvid_keyframes(text):
    return [i-3 for i,line in enumerate(text.splitlines()) if line and line[0] == 'i']


def parse_keyframes(path):
    with open(path) as file_object:
        text = file_object.read()
    if text.find('# XviD 2pass stat file')>=0:
        frames = parse_scxvid_keyframes(text)
    else:
        raise PrassError('Unsupported keyframes type')
    if 0 not in frames:
        frames.insert(0, 0)
    return frames


class Timecodes(object):
    TIMESTAMP_END = 1
    TIMESTAMP_START = 2

    def __init__(self, times, default_fps):
        super(Timecodes, self).__init__()
        self.times = times
        self.default_frame_duration = 1000.0 / default_fps if default_fps else None

    def get_frame_time(self, number, kind=None):
        if kind == self.TIMESTAMP_START:
            prev = self.get_frame_time(number-1)
            curr = self.get_frame_time(number)
            return prev + int(round((curr - prev) / 2.0))
        elif kind == self.TIMESTAMP_END:
            curr = self.get_frame_time(number)
            after = self.get_frame_time(number+1)
            return curr + int(round((after - curr) / 2.0))

        try:
            return self.times[number]
        except IndexError:
            if not self.default_frame_duration:
                raise ValueError("Cannot calculate frame timestamp without frame duration")
            past_end, last_time = number, 0
            if self.times:
                past_end, last_time = (number - len(self.times) + 1), self.times[-1]

            return int(round(past_end * self.default_frame_duration + last_time))

    def get_frame_number(self, ms, kind=None):
        if kind == self.TIMESTAMP_START:
            return self.get_frame_number(ms - 1) + 1
        elif kind == self.TIMESTAMP_END:
            return self.get_frame_number(ms - 1)

        if self.times and self.times[-1] >= ms:
            return bisect.bisect_left(self.times, ms)

        if not self.default_frame_duration:
            raise ValueError("Cannot calculate frame for this timestamp without frame duration")

        if ms < 0:
            return int(math.floor(ms / self.default_frame_duration))

        last_time = self.times[-1] if self.times else 0
        return int((ms - last_time) / self.default_frame_duration) + len(self.times)

    @classmethod
    def _convert_v1_to_v2(cls, default_fps, overrides):
        # start, end, fps
        overrides = [(int(x[0]), int(x[1]), float(x[2])) for x in overrides]
        if not overrides:
            return []

        fps = [default_fps] * (overrides[-1][1] + 1)
        for start, end, fps in overrides:
            fps[start:end + 1] = [fps] * (end - start + 1)

        v2 = [0]
        for d in (1000.0 / f for f in fps):
            v2.append(v2[-1] + d)
        return v2

    @classmethod
    def parse(cls, text):
        lines = text.splitlines()
        if not lines:
            return []
        first = lines[0].lower().lstrip()
        if first.startswith('# timecode format v2'):
            tcs = [x for x in lines[1:]]
            return Timecodes(tcs, None)
        elif first.startswith('# timecode format v1'):
            default = float(lines[1].lower().replace('assume ', ""))
            overrides = (x.split(',') for x in lines[2:])
            return Timecodes(cls._convert_v1_to_v2(default, overrides), default)
        else:
            raise PrassError('This timecodes format is not supported')

    @classmethod
    def from_file(cls, path):
        with open(path) as file:
            return cls.parse(file.read())

    @classmethod
    def cfr(cls, fps):
        return Timecodes([], default_fps=fps)
