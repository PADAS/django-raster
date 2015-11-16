import xml.etree.ElementTree as ET

from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
import raster.models as models

IGNORE_LABEL = ['no data']

class Command(BaseCommand):
    help = 'Load a legend from a qml file'

    def add_arguments(self, parser):
        parser.add_argument('legend_name', type=str)
        parser.add_argument('legend_file', type=str)

    def handle(self, *args, **options):
        legend_name = options['legend_name']
        legend_file = options['legend_file']

        self.parse_and_import(legend_name, legend_file)

        self.stdout.write('Successfully imported legend "%s"' % legend_name)

    def parse_and_import(self, legend_name, legend_file):
        tree = ET.parse(legend_file)
        root = tree.getroot()
        colors = root.findall('./pipe/rasterrenderer/colorPalette/paletteEntry')

        with transaction.atomic():
            try:
                legend = models.Legend.objects.get(title=legend_name)
                raise CommandError('legend already exists')
            except models.Legend.DoesNotExist:
                pass

            legend = models.Legend(title=legend_name)
            legend.save()

            for pe in colors:
                pe_value = pe.attrib['value']
                pe_color = pe.attrib['color']
                pe_label = pe.attrib['label']
                if pe_label.lower() in IGNORE_LABEL:
                    continue
                pe_expression = 'x == {0}'.format(pe_value)
                semantic = models.LegendSemantics(name=pe_label)
                semantic.save()

                legend_entry = models.LegendEntry(semantics=semantic,
                                                  expression=pe_expression,
                                                  color=pe_color)
                legend_entry.save()
                legend.entries.add(legend_entry)


            legend.save()


