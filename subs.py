import codecs
import os
import bisect
from itertools import izip
from common import PrassError
from collections import OrderedDict


def parse_ass_time(string):
    hours, minutes, seconds = map(float, string.split(':'))
    return hours*3600+minutes*60+seconds


def format_time(seconds):
    cs = round(seconds * 100)
    return u'{0}:{1:02d}:{2:02d}.{3:02d}'.format(
            int(cs // 360000),
            int((cs // 6000) % 60),
            int((cs // 100) % 60),
            int(cs % 100))


class AssStyle(object):
    def __init__(self, name, definition):
        self.name = name
        self.definition = definition

    @classmethod
    def from_string(cls, text):
        split = text.split(':', 1)[1].split(',', 1)
        return cls(name=split[0].strip(), definition=split[1].strip())


class AssEvent(object):
    __slots__ = (
        "kind",
        "layer",
        "start",
        "end",
        "style",
        "actor",
        "margin_left",
        "margin_right",
        "margin_vertical",
        "effect",
        "text"
    )

    def __init__(self, start, end, text, kind='Dialogue', layer=0, style='Default', actor='',
                 margin_left=0, margin_right=0, margin_vertical=0, effect=''):
        self.kind = kind
        self.layer = layer
        self.start = start
        self.end = end
        self.style = style
        self.actor = actor
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_vertical = margin_vertical
        self.effect = effect
        self.text = text

    @classmethod
    def from_text(cls, text):
        split = text.split(':', 1)
        kind = split[0]

        split = [x.strip() for x in split[1].split(',', 9)]
        return cls(
            kind=kind,
            layer=int(split[0]),
            start=parse_ass_time(split[1]),
            end=parse_ass_time(split[2]),
            style=split[3],
            actor=split[4],
            margin_left=split[5],
            margin_right=split[6],
            margin_vertical=split[7],
            effect=split[8],
            text=split[9]
        )

    def __unicode__(self):
        return u'{0}: {1},{2},{3},{4},{5},{6},{7},{8},{9},{10}'.format(self.kind, self.layer,
                                                                       format_time(self.start),
                                                                       format_time(self.end),
                                                                       self.style, self.actor,
                                                                       self.margin_left, self.margin_right,
                                                                       self.margin_vertical, self.effect,
                                                                       self.text)

    @property
    def is_comment(self):
        return self.kind.lower() == 'comment'

    def collides_with(self, other):
        if self.start < other.start:
            return self.end > other.start
        return self.start < other.end


class AssScript(object):
    def __init__(self, script_info, styles, events):
        super(AssScript, self).__init__()
        self._script_info = script_info
        self._styles = styles
        self._events = events

    @classmethod
    def from_ass_stream(cls, file_object):
        script_info, styles, events = [], OrderedDict(), []

        parse_script_info_line = lambda x: script_info.append(x)

        def parse_styles_line(text):
            style = AssStyle.from_string(text)
            styles[style.name] = style

        parse_event_line = lambda x: events.append(AssEvent.from_text(x))

        parse_function = None
        for line in file_object:
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            if low == u'[script info]':
                parse_function = parse_script_info_line
            elif low == u'[v4+ styles]':
                parse_function = parse_styles_line
            elif low == u'[events]':
                parse_function = parse_event_line
            elif low.startswith(u'format:'):
                continue  # ignore it
            elif not parse_function:
                raise PrassError("That's some invalid ASS script")
            else:
                try:
                    parse_function(line)
                except Exception as e:
                    raise PrassError("That's some invalid ASS script: {0}".format(e.message))
        return cls(script_info, styles, events)

    @classmethod
    def from_ass_file(cls, path):
        try:
            with codecs.open(path, encoding='utf-8-sig') as script:
                return cls.from_ass_stream(script)
        except IOError:
            raise PrassError("Script {0} not found".format(path))

    @classmethod
    def from_srt_stream(cls, file_object):
        events = []
        parse_time = lambda x: parse_ass_time(x.replace(',', '.'))

        for srt_event in file_object.read().replace('\r\n', '\n').split('\n\n'):
            if not srt_event:
                continue
            lines = srt_event.split('\n', 2)
            times = lines[1].split('-->')
            events.append(AssEvent(
                start=parse_time(times[0].rstrip()),
                end=parse_time(times[1].lstrip()),
                text=lines[2].replace('\n', r'\N')
            ))
        styles = OrderedDict()#
        styles['Default'] = AssStyle('Default', 'Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1')
        script_info = ['Script converted by Prass']
        return cls(script_info, styles, events)

    def to_ass_stream(self, file_object):
        lines = []
        if self._script_info:
            lines.append(u'[Script Info]')
            lines.extend(self._script_info)
            lines.append('')

        if self._styles:
            lines.append(u'[V4+ Styles]')
            lines.append(u'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding')
            lines.extend('Style: {0},{1}'.format(style.name, style.definition) for style in self._styles.itervalues())
            lines.append('')

        if self._events:
            lines.append(u'[Events]')
            lines.append(u'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text')
            lines.extend(map(unicode, self._events))
        lines.append('')
        file_object.write(unicode(os.linesep).join(lines))

    def to_ass_file(self, path):
        with codecs.open(path, encoding='utf-8-sig', mode='w') as script:
            self.to_ass_stream(script)

    def append_styles(self, other, clean):
        if clean:
            self._styles = OrderedDict()
        for style in other.itervalues():
            self._styles[style.name] = style

    def sort_events(self, key, descending):
        self._events.sort(key=key, reverse=descending)

    def tpp(self, styles, lead_in, lead_out, max_overlap, max_gap, adjacent_bias,
            keyframes_list, timecodes, kf_before_start, kf_after_start, kf_before_end, kf_after_end):
        def get_distance_to_closest_kf(timestamp, keytimes):
            idx = bisect.bisect_left(keytimes, timestamp)
            if idx == 0:
                kf = keytimes[0]
            elif idx == len(keytimes):
                kf = keytimes[-1]
            else:
                before = keytimes[idx - 1]
                after = keytimes[idx]
                kf = after if after - timestamp < timestamp - before else before
            return kf - timestamp

        events_iter = (e for e in self._events if not e.is_comment)
        if styles:
            styles = set(s.lower() for s in styles)
            events_iter = (e for e in events_iter if e.style.lower() in styles)

        events_list = sorted(events_iter, key=lambda x: x.start)
        broken = next((e for e in events_list if e.start > e.end), None)
        if broken:
            raise PrassError("One of the lines in the file ({0}) has negative duration. Aborting.".format(broken))

        # all times are converted to seconds because that's how we roll
        if lead_in:
            lead_in /= 1000.0
            sorted_by_end = sorted(events_list, key=lambda x: x.end)
            for idx, event in enumerate(sorted_by_end):
                initial = event.start - lead_in
                for other in reversed(sorted_by_end[:idx]):
                    if other.end <= initial:
                        break
                    if not event.collides_with(other):
                        initial = max(initial, other.end)
                event.start = initial

        if lead_out:
            lead_out /= 1000.0
            for idx, event in enumerate(events_list):
                initial = event.end + lead_out
                for other in events_list[idx:]:
                    if other.start > initial:
                        break
                    if not event.collides_with(other):
                        initial = min(initial, other.start)
                event.end = initial

        if max_overlap or max_gap:
            bias = adjacent_bias/100.0
            max_gap /= 1000.0
            max_overlap /= 1000.0

            for previous, current in izip(events_list, events_list[1:]):
                distance = current.start - previous.end
                if (distance < 0 and -distance <= max_overlap) or (distance > 0 and distance <= max_gap):
                    new_time = previous.end + distance * bias
                    current.start = new_time
                    previous.end = new_time

        if kf_before_start or kf_after_start or kf_before_end or kf_after_end:
            kf_before_start /= 1000.0
            kf_after_start /= 1000.0
            kf_before_end /= 1000.0
            kf_after_end /= 1000.0

            keytimes = [timecodes.get_frame_time(x) for x in keyframes_list]
            for event in events_list:
                start_distance = get_distance_to_closest_kf(event.start, keytimes)
                end_distance = get_distance_to_closest_kf(event.end + timecodes.get_frame_size(event.end), keytimes)

                if (start_distance < 0 and -start_distance < kf_before_start) or (start_distance > 0 and start_distance < kf_after_start):
                    event.start += start_distance
                if (end_distance < 0 and -end_distance < kf_before_end) or (end_distance > 0 and end_distance < kf_after_end):
                    event.end += end_distance

    def cleanup(self, drop_comments, drop_empty_lines, drop_unused_styles, drop_actors, drop_effects):
        if drop_comments:
            self._events = [e for e in self._events if not e.is_comment]

        if drop_empty_lines:
            self._events = [e for e in self._events if e.text]

        if drop_unused_styles:
            used_styles = set(e.style for e in self._events)
            for style_name in self._styles.keys():
                if style_name not in used_styles:
                    del self._styles[style_name]

        if drop_actors:
            for event in self._events:
                event.actor = ''

        if drop_effects:
            for event in self._events:
                event.effect = ''

    def shift(self, shift, shift_start, shift_end):
        for event in self._events:
            if shift_start:
                event.start = max(event.start + shift, 0)
            if shift_end:
                event.end = max(event.end + shift, 0)
