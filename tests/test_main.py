# -*- coding: utf-8 -*-
import unittest

import prass
import common


class TestFpsParsing(unittest.TestCase):
    def test_number(self):
        self.assertEqual(23.976, prass.parse_fps_string("23.976"))
        self.assertEqual(24, prass.parse_fps_string("24"))

    def test_division(self):
        self.assertAlmostEqual(23.976, prass.parse_fps_string("24000/1001"), places=3)
        self.assertAlmostEqual(29.970, prass.parse_fps_string("30000/1001"), places=3)

    def test_invalid(self):
        self.assertRaises(common.PrassError, lambda: prass.parse_fps_string("24000/1001/1"))
        self.assertRaises(common.PrassError, lambda: prass.parse_fps_string("not a number"))


class TestShiftParsing(unittest.TestCase):
    def test_number(self):
        self.assertAlmostEqual(-1000, prass.parse_shift_string("-1"))
        self.assertAlmostEqual(1500, prass.parse_shift_string("1.5"))
        self.assertAlmostEqual(12, prass.parse_shift_string("12ms"))
        self.assertAlmostEqual(2500, prass.parse_shift_string("2.5s"))

    def test_timestamp(self):
        self.assertAlmostEqual(61000, prass.parse_shift_string("1:1"))
        self.assertAlmostEqual(61530, prass.parse_shift_string("1:1.53"))
        self.assertAlmostEqual(61530, prass.parse_shift_string("1:1.53"))
        self.assertAlmostEqual(-61530, prass.parse_shift_string("-1:1.53"))
        self.assertAlmostEqual((12 * 3600 + 15 * 60) * 1000 + 23128, prass.parse_shift_string("12:15:23.128"))

    def test_invalid(self):
        self.assertRaises(common.PrassError, lambda: prass.parse_shift_string("1:1:1:1"))
        self.assertRaises(common.PrassError, lambda: prass.parse_shift_string("123seconds"))
        self.assertRaises(common.PrassError, lambda: prass.parse_shift_string("not a number"))


class TestResolutionParsing(unittest.TestCase):
    def test_templates(self):
        self.assertEqual((1280, 720), prass.parse_resolution_string("720p"))
        self.assertEqual((1920, 1080), prass.parse_resolution_string("1080p"))

    def test_full_definition(self):
        self.assertEqual((1280,720), prass.parse_resolution_string("1280:720"))
        self.assertEqual((848,480), prass.parse_resolution_string("848x480"))

    def test_invalid(self):
        self.assertRaises(common.PrassError, lambda: prass.parse_resolution_string("720"))
        self.assertRaises(common.PrassError, lambda: prass.parse_resolution_string("1920.1080"))
        self.assertRaises(common.PrassError, lambda: prass.parse_resolution_string("1963p"))
        self.assertRaises(common.PrassError, lambda: prass.parse_resolution_string("not a number"))
