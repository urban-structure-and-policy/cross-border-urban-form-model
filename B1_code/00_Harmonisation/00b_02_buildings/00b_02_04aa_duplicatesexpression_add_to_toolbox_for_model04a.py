from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingOutputString,
    QgsProcessingException,
)
from qgis import processing
from collections import Counter

class ExtractDuplicates(QgsProcessingAlgorithm):
    INPUT_LAYER = 'INPUT_LAYER'
    OUTPUT_EXPRESSION = 'OUTPUT_EXPRESSION'

    def initAlgorithm(self, config=None):
        # Input parameter: vector layer
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_LAYER,
                self.tr('Input Layer'),
                [QgsProcessing.TypeVector]
            )
        )
        
        # Output: expression string
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_EXPRESSION,
                self.tr('Expression for Duplicates')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Get the input layer
        layer = self.parameterAsVectorLayer(parameters, self.INPUT_LAYER, context)
        if not layer:
            raise QgsProcessingException(self.tr('Invalid input layer'))

        # Define the field to check for duplicates
        field_name = 'osm_id'
        all_rows = [feat[field_name] for feat in layer.getFeatures()]
        
        # Identify duplicates
        value_counts = Counter(all_rows)
        duplicates = [value for value, count in value_counts.items() if count > 1]
        
        # Generate the expression for duplicates
        duplicates_str = ", ".join([f"'{value}'" for value in duplicates])
        expression = f'"{field_name}" IN ({duplicates_str})'

        # Return the expression as output
        return {self.OUTPUT_EXPRESSION: expression}

    def name(self):
        return 'extractduplicates'

    def displayName(self):
        return self.tr('Extract Duplicates Expression')

    def group(self):
        return self.tr('Custom Scripts')

    def groupId(self):
        return 'customscripts'

    def createInstance(self):
        return ExtractDuplicates()

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
