import numpy

from django.contrib.gis.geos import Polygon
from django.test.utils import override_settings
from raster.const import WEB_MERCATOR_SRID
from raster.valuecount import RasterAggregationException, aggregator

from .raster_testcase import RasterTestCase


@override_settings(RASTER_TILE_CACHE_TIMEOUT=0)
class RasterValueCountTests(RasterTestCase):

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
        # Drop nodata value from expected data
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
        # Drop nodata value (aggregation uses masked arrays)
        expected.pop(255)

        # Confirm clipped count
        self.assertEqual(
            self.rasterlayer.value_count(bbox),
            {str(k): v for k, v in expected.items()}
        )
        # For db based counts, remove nodata
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
        # Drop nodata value (aggregation uses masked arrays)
        expected.pop('255')

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

        # Drop nodata value (aggregation uses masked arrays)
        expected.pop(255)

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
            self.continuous_expected_histogram
        )


class RasterAggregatorTests(RasterTestCase):

    def test_layer_with_no_tiles(self):
        result = aggregator(
            layer_dict={'a': self.rasterlayer.id, 'b': self.empty_rasterlayer.id},
            formula='a*b'
        )
        self.assertDictEqual(result, {})

    def test_layer_discrete_grouping(self):
        result = aggregator(
            layer_dict={'a': self.rasterlayer.id},
            formula='a',
            grouping='discrete'
        )
        self.assertDictEqual(
            result,
            {str(k): v for k, v in self.expected_totals.items()}
        )

    def test_layer_continuous_grouping(self):
        result = aggregator(
            layer_dict={'a': self.rasterlayer.id},
            formula='a',
            grouping='continuous'
        )
        self.assertDictEqual(
            result,
            self.continuous_expected_histogram
        )

    def test_layer_with_legend_grouping(self):
        # Use a legend with simple int expression
        result = aggregator(
            layer_dict={'a': self.rasterlayer.id},
            formula='a',
            grouping=self.legend.id
        )
        self.assertDictEqual(
            result,
            {'2': self.expected_totals[2]}
        )
        # Use a legend with formula expression
        result = aggregator(
            layer_dict={'a': self.rasterlayer.id},
            formula='a',
            grouping=self.legend_with_expression.id
        )
        self.assertDictEqual(
            result,
            {'(x >= 2) & (x < 5)': self.expected_totals[2] + self.expected_totals[3] + self.expected_totals[4]}
        )

    def test_valuecount_exception(self):
        with self.assertRaises(RasterAggregationException):
            aggregator(
                layer_dict={'a': self.rasterlayer.id},
                formula='a',
                grouping='unknown'
            )
