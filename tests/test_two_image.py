import os
import unittest

from plio.io.io_controlnetwork import to_isis
from plio.io.io_controlnetwork import write_filelist

from autocnet.examples import get_path
from autocnet.matcher.suppression_funcs import error
from autocnet.graph.network import CandidateGraph

import pandas as pd
import numpy as np


class TestTwoImageMatching(unittest.TestCase):
    """
    Feature: As a user
        I wish to automatically match two images to
        Generate an ISIS control network

        Scenario: Match two images
            Given a manually specified adjacency structure named two_image_adjacency.json
            When read create an adjacency graph
            Then extract image data and attribute nodes
            And find features and descriptors
            And apply a FLANN matcher
            Then create a C object from the graph matches
            Then output a control network
    """

    def setUp(self):
        self.serial_numbers = {'AS15-M-0295_SML.png': '1971-07-31T01:24:11.754',
                               'AS15-M-0296_SML.png': '1971-07-31T01:24:36.970',
                               'AS15-M-0297_SML.png': '1971-07-31T01:25:02.243',
                               'AS15-M-0298_SML.png': '1971-07-31T01:25:27.457',
                               'AS15-M-0299_SML.png': '1971-07-31T01:25:52.669',
                               'AS15-M-0300_SML.png': '1971-07-31T01:26:17.923'}

        for k, v in self.serial_numbers.items():
            self.serial_numbers[k] = 'APOLLO15/METRIC/{}'.format(v)

    def test_two_image(self):
        # Step: Create an adjacency graph
        adjacency = get_path('two_image_adjacency.json')
        basepath = get_path('Apollo15')
        cg = CandidateGraph.from_adjacency(adjacency, basepath=basepath)
        self.assertEqual(2, cg.number_of_nodes())
        self.assertEqual(1, cg.number_of_edges())

        # Step: Extract image data and attribute nodes
        cg.extract_features(extractor_method='sift', extractor_parameters={"nfeatures":500})
        for i, node in cg.nodes.data('data'):
            self.assertIn(node.nkeypoints, range(490, 510))

        # Step: Compute the coverage ratios
        for i, node in cg.nodes.data('data'):
            ratio = node.coverage()
            self.assertTrue(0.93 < round(ratio, 8) < 0.96)

        cg.decompose_and_match(k=2, maxiteration=2)
        self.assertTrue(isinstance(cg.edges[0,1]['data'].smembership, np.ndarray))

        # Create fundamental matrix
        cg.compute_fundamental_matrices()

        for s, d, e in cg.edges.data('data'):
            assert isinstance(e['fundamental_matrix'], np.ndarray)
            err = e.compute_fundamental_error(clean_keys=['fundamental'])
            assert isinstance(err, pd.Series)
            matches, _ = e.clean(clean_keys=['fundamental'])
            assert matches.index.all() == err.index.all()

        # Apply AMNS
        cg.suppress(k=30, suppression_func=error)

        # Step: Compute subpixel offsets for candidate points
        cg.subpixel_register(clean_keys=['suppression'], tiled=True)
        cg.subpixel_register(clean_keys=['suppression'])

    def tearDown(self):
        try:
            os.remove('TestTwoImageMatching.net')
            os.remove('fromlist.lis')
        except: pass
