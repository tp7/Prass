# -*- coding: utf-8 -*-
import unittest
import os
import codecs
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import subs


def get_script_path(name):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(script_dir, name)


def script_to_string(ass_script):
    buffer = StringIO()
    ass_script.to_ass_stream(buffer)
    return buffer.getvalue()


def load_script(name):
    with codecs.open(get_script_path(name), encoding="utf-8-sig") as input_file:
        script = input_file.read()
        # Windows is weid so you need to use \n internally
        return script.replace("\r\n", "\n")
        


class TestSubs(unittest.TestCase):
    maxDiff = None

    def test_ass_time_parsing(self):
        self.assertEqual(150, subs.parse_ass_time("00:00:00.15"))
        self.assertEqual(12150, subs.parse_ass_time("00:00:12.15"))
        self.assertEqual(132150, subs.parse_ass_time("00:02:12.15"))

    def test_srt_time_parsing(self):
        self.assertEqual(132150, subs.parse_srt_time("00:02:12,150"))

    def test_srt_line_parsing(self):
        self.assertEqual(subs.srt_line_to_ass('<u>underlined</u>\n 0<b>1<i>2<s> many </i>3</s>4</b>5'), 
                        '{\\u1}underlined{\\u0}\\N 0{\\b1}1{\\i1}2{\\s1} many {\\i0}3{\\s0}4{\\b0}5')
        self.assertEqual(subs.srt_line_to_ass('<b>bold</b>, <i>italic</i>, <s>strikeout</s>'), 
                        '{\\b1}bold{\\b0}, {\\i1}italic{\\i0}, {\\s1}strikeout{\\s0}')
        self.assertEqual(subs.srt_line_to_ass('<font color="#FF0000">text</font>'), 
                        '{\\c&H0000FF&}text{\\c&HFFFFFF&}')

    def test_cleanup(self):
        # this test also ensures that we leave two [Graphics] sections in their proper positions
        ass_script = subs.AssScript.from_ass_file(get_script_path("test_script.ass"))
        ass_script.cleanup(drop_actors=True, drop_comments=True, drop_effects=True,
                           drop_empty_lines=True, drop_unused_styles=True, drop_spacing=True, drop_sections=["[Fonts]"])

        self.assertEqual(load_script("cleanup_script.ass"), script_to_string(ass_script))

    def test_noop(self):
        ass_script = subs.AssScript.from_ass_file(get_script_path("test_script.ass"))
        self.assertEqual(load_script("test_script.ass"), script_to_string(ass_script))


class TestStyles(unittest.TestCase):
    def test_resample(self):
        source = subs.AssStyle.from_string(u"Default,Arial,36,&H00FFFFFF,&H000000FF,&H00020713,&H00000000,-1,0,0,0,100,100,0,0,1,1.7,0,2,0,0,28,1")
        source.resample(from_width=848, from_height=480, to_width=1920, to_height=1080)
        self.assertEqual(source.definition, u"Arial,81,&H00FFFFFF,&H000000FF,&H00020713,&H00000000,-1,0,0,0,100,100,0,0,1,3.825,0,2,0,0,63,1")


class TestScriptInfoSection(unittest.TestCase):
    def test_comments(self):
        section = subs.ScriptInfoSection()
        section.parse_line("; random comment")
        section.parse_line("; another comment")
        self.assertEqual(["; random comment", "; another comment"], section.format_section())

    def test_order(self):
        section = subs.ScriptInfoSection()
        section.parse_line("; random")
        section.parse_line("Property: 2")
        section.parse_line("; comment")
        section.parse_line("Another: property")
        self.assertEqual(["; random", "Property: 2", "; comment", "Another: property"],
                         section.format_section())

    def test_resolution(self):
        section = subs.ScriptInfoSection()
        self.assertEqual((None, None), section.get_resolution())

        section.parse_line("PlayResY: 480")
        section.parse_line("PlayResX: 848")
        self.assertEqual((848, 480), section.get_resolution())

        section.set_resolution(1920, 1080)
        self.assertEqual(["PlayResY: 1080", "PlayResX: 1920"], section.format_section())
        self.assertEqual((1920, 1080), section.get_resolution())

    def test_setting_property(self):
        section = subs.ScriptInfoSection()
        section.set_property("Random", 12.5)
        section.set_property("teSt", "property")
        self.assertEqual(["Random: 12.5", "teSt: property"], section.format_section())

        section.set_property("Random", "other value")
        self.assertEqual(["Random: other value", "teSt: property"], section.format_section())

    def test_getting_property(self):
        section = subs.ScriptInfoSection()
        section.parse_line("Random: property")

        self.assertEqual("property", section.get_property("Random"))

        self.assertRaises(KeyError, lambda: section.get_property("property"))
        self.assertRaises(KeyError, lambda: section.get_property("rAnDom"))


