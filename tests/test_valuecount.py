import numpy

from django.contrib.gis.geos import Polygon
from django.test.utils import override_settings
from raster.const import WEB_MERCATOR_SRID
from raster.valuecount import aggregator

from .raster_testcase import RasterTestCase


@override_settings(RASTER_TILE_CACHE_TIMEOUT=0)
class RasterValueCountTests(RasterTestCase):

    def setUp(self):
        super(RasterValueCountTests, self).setUp()
        # Precompute expected totals from value count
        expected = {}
        for tile in self.rasterlayer.rastertile_set.filter(tilez=11):
            val, counts = numpy.unique(tile.rast.bands[0].data(), return_counts=True)
            for pair in zip(val, counts):
                if pair[0] in expected:
                    expected[pair[0]] += pair[1]
                else:
                    expected[pair[0]] = pair[1]

        self.expected_totals = expected

    def test_value_count_no_geom(self):
        self.assertEqual(
            self.rasterlayer.value_count(),
            {str(k): v for k, v in self.expected_totals.items()}
        )

    def test_value_count_with_geom_covering_all(self):
        # Set extent covering all tiles
        extent = (
            -10036039.001754418, 1028700.0747658457,
            -3016471.122513413, 5548267.9540068507,
        )

        # Create polygon from extent
        bbox = Polygon.from_bbox(extent)
        bbox.srid = WEB_MERCATOR_SRID

        # Confirm global count
        self.assertEqual(
            self.rasterlayer.value_count(bbox),
            {str(key): val for key, val in self.expected_totals.items()}
        )
        self.assertEqual(
            self.rasterlayer.db_value_count(bbox),
            self.expected_totals
        )

    def test_value_count_with_geom_covering_single_tile(self):
        # Get extent from single tile
        tile = self.rasterlayer.rastertile_set.get(tilez=11, tilex=552, tiley=858)
        extent = tile.rast.extent

        # Create polygon from extent, transform into different projection
        bbox = Polygon.from_bbox(extent)
        bbox.srid = WEB_MERCATOR_SRID
        bbox.transform(3086)

        # Compute expected counts for this tile
        expected = {}
        val, counts = numpy.unique(tile.rast.bands[0].data(), return_counts=True)
        for pair in zip(val, counts):
            if pair[0] in expected:
                expected[pair[0]] += pair[1]
            else:
                expected[pair[0]] = pair[1]

        # Confirm clipped count
        self.assertEqual(
            self.rasterlayer.value_count(bbox),
            {str(k): v for k, v in expected.items()}
        )
        self.assertEqual(
            self.rasterlayer.db_value_count(bbox),
            expected
        )

    def test_area_calculation_with_geom_covering_single_tile(self):
        # Get extent from single tile
        tile = self.rasterlayer.rastertile_set.get(tilez=11, tilex=552, tiley=858)
        extent = tile.rast.extent

        # Create polygon from extent in default projection
        bbox = Polygon.from_bbox(extent)
        bbox.srid = WEB_MERCATOR_SRID
        bbox.transform(3086)

        expected = {}
        val, counts = numpy.unique(tile.rast.bands[0].data(), return_counts=True)
        for pair in zip(val, counts):
            pair = (str(pair[0]), pair[1])
            if pair[0] in expected:
                expected[pair[0]] += pair[1] * 1.44374266645
            else:
                expected[pair[0]] = pair[1] * 1.44374266645

        # Confirm clipped count
        result = self.rasterlayer.value_count(bbox, area=True)
        for k, v in result.items():
            self.assertAlmostEqual(v, expected[k], 5)

    def test_value_count_at_lower_zoom(self):
        # Precompute expected totals from value count
        expected = {}
        for tile in self.rasterlayer.rastertile_set.filter(tilez=9):
            val, counts = numpy.unique(tile.rast.bands[0].data(), return_counts=True)
            for pair in zip(val, counts):
                if pair[0] in expected:
                    expected[pair[0]] += pair[1]
                else:
                    expected[pair[0]] = pair[1]

        self.assertEqual(
            self.rasterlayer.value_count(zoom=9),
            {str(k): v for k, v in expected.items()}
        )
        self.assertEqual(
            self.rasterlayer.db_value_count(zoom=9),
            expected
        )

    def test_value_count_for_continuous_raster(self):
        self.rasterlayer.datatype = 'co'
        self.rasterlayer.save()
        self.assertEqual(
            self.rasterlayer.value_count(),
            {
                '(0.0, 0.90000000000000002)': 221445,
                '(8.0999999999999996, 9.0)': 2977,
                '(1.8, 2.7000000000000002)': 56,
                '(0.90000000000000002, 1.8)': 695,
                '(2.7000000000000002, 3.6000000000000001)': 4131,
                '(7.2000000000000002, 8.0999999999999996)': 1350,
                '(3.6000000000000001, 4.5)': 31490
            }
        )


class RasterAggregatorTests(RasterTestCase):

    def test_layer_with_no_tiles(self):
        result = aggregator(
            layer_dict={'a': self.rasterlayer.id, 'b': self.empty_rasterlayer.id},
            zoom=7,
            formula='a*b'
        )
        self.assertDictEqual(result, {})
