import os, sys, unittest

# test this version of Wrangler
curdir = os.path.dirname(__file__)
sys.path.insert(1, os.path.normpath(os.path.join(curdir, "..", "..")))

import Wrangler

class TestTransitNode(unittest.TestCase):

    def setUp(self):
        """ Initialize the TransitNetwork and read in the unittests dir
        """
        self.embarc = Wrangler.Node(16511)
        self.embarc.attr["ACCESS"] = 2
        
        self.invalid = Wrangler.Node(1)

    def test_transit_node_description(self):

        self.assertEqual(self.embarc.description(),"Embarcadero BART")
        self.assertEqual(self.invalid.description(), None)

    def test_transit_node_boards_disallowed(self):
        self.assertEqual(self.embarc.boardsDisallowed(), True)
        self.assertEqual(self.invalid.boardsDisallowed(), False)


if __name__ == '__main__':
    unittest.main()