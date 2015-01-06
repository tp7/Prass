from common import PrassError
import bisect


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
    def __init__(self, times, default_fps):
        super(Timecodes, self).__init__()
        self.times = times
        self.default_frame_duration = 1.0 / default_fps if default_fps else None

    def get_frame_time(self, number):
        try:
            return self.times[number]
        except IndexError:
            if not self.default_frame_duration:
                return self.get_frame_time(len(self.times)-1)
            if self.times:
                return self.times[-1] + (self.default_frame_duration) * (number - len(self.times) + 1)
            else:
                return number * self.default_frame_duration

    def get_frame_number(self, timestamp):
        if (not self.times or self.times[-1] < timestamp) and self.default_frame_duration:
            return int((timestamp - sum(self.times)) / self.default_frame_duration)
        return bisect.bisect_left(self.times, timestamp)

    def get_frame_size(self, timestamp):
        try:
            number = bisect.bisect_left(self.times, timestamp)
        except:
            return self.default_frame_duration

        c = self.get_frame_time(number)

        if number == len(self.times):
            p = self.get_frame_time(number - 1)
            return c - p
        else:
            n = self.get_frame_time(number + 1)
            return n - c

    @classmethod
    def _convert_v1_to_v2(cls, default_fps, overrides):
        # start, end, fps
        overrides = [(int(x[0]), int(x[1]), float(x[2])) for x in overrides]
        if not overrides:
            return []

        fps = [default_fps] * (overrides[-1][1] + 1)
        for o in overrides:
            fps[o[0]:o[1] + 1] = [o[2]] * (o[1] - o[0] + 1)

        v2 = [0]
        for d in (1.0 / f for f in fps):
            v2.append(v2[-1] + d)
        return v2

    @classmethod
    def parse(cls, text):
        lines = text.splitlines()
        if not lines:
            return []
        first = lines[0].lower().lstrip()
        if first.startswith('# timecode format v2'):
            tcs = [float(x) / 1000.0 for x in lines[1:]]
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
        class CfrTimecodes(object):
            def __init__(self, fps):
                self.frame_duration = 1.0 / fps

            def get_frame_time(self, number):
                return number * self.frame_duration

            def get_frame_size(self, timestamp):
                return self.frame_duration

            def get_frame_number(self, timestamp):
                return int(timestamp / self.frame_duration)

        return CfrTimecodes(fps)