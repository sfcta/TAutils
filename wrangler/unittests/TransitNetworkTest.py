import os, sys, unittest

# test this version of Wrangler
curdir = os.path.dirname(__file__)
sys.path.insert(1, os.path.normpath(os.path.join(curdir, "..", "..")))

import Wrangler

class TestTransitNetwork(unittest.TestCase):

    def setUp(self):
        """ Initialize the TransitNetwork and read in the unittests dir
        """
        self.tn = Wrangler.TransitNetwork()
        thisdir = os.path.dirname(os.path.realpath(__file__))

        self.tn.mergeDir(thisdir)

    def test_transit_network_iterator(self):
        count = 0
        for line in self.tn:
            count += 1
            self.assertTrue(isinstance(line,Wrangler.TransitLine))
        self.assertEqual(count,2)

        count = 0
        for line in self.tn:
            count += 1
            self.assertTrue(isinstance(line,Wrangler.TransitLine))
        self.assertEqual(count,2)

    def test_transit_line_iterator(self):
        count = 0
        for stop in self.tn.line("TEST_A"):
            count += 1
            self.assertTrue(isinstance(stop,int))
        self.assertEqual(count,10)

    def test_transit_line_hasLink(self):
        self.assertTrue(self.tn.line("TEST_A").hasLink(2,3))
        self.assertTrue(self.tn.line("TEST_A").hasLink(-2,-3))
        self.assertFalse(self.tn.line("TEST_A").hasLink(3,2))
        self.assertFalse(self.tn.line("TEST_A").hasLink(2,4))

    def test_transit_line_hasSegment(self):
        self.assertTrue(self.tn.line("TEST_A").hasSegment(2,3))
        self.assertTrue(self.tn.line("TEST_A").hasSegment(-2,-3))
        self.assertFalse(self.tn.line("TEST_A").hasSegment(3,2))
        self.assertTrue(self.tn.line("TEST_A").hasSegment(2,4))

    def test_transit_line_extendLine(self):
        self.assertRaises(ValueError,
                          self.tn.line("TEST_B").extendLine,
                          14, [24,25,26,-27,28], False)

        self.tn.line("TEST_B").extendLine(-14,[24,25,26,-27,28], beginning=False)
        self.assertEqual(len(self.tn.line("TEST_B").n),8)
        # for stop in self.tn.line("TEST_B"): print stop

        # test doing an extend at the beginning

    def test_transit_line_index(self):
        self.assertEqual(self.tn.line("TEST_A").n.index(4), 3)

if __name__ == '__main__':
    unittest.main()