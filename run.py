# -*- coding: utf-8 -*-

# * Copyright (c) 2009-2018. Authors: see NOTICE file.
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *      http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__author__          = "Marée Raphaël <raphael.maree@ulg.ac.be>" 
__contributors__    = ["Stévens Benjamin <b.stevens@ulg.ac.be>"]                
__copyright__       = "Copyright 2010-2018 University of Liège, Belgium, http://www.cytomine.be/"


from operator import attrgetter

import os
import cv2
import numpy as np
from cytomine import CytomineJob
from cytomine.models import ImageInstanceCollection, AnnotationCollection, Annotation
from cytomine.utilities.reader import Bounds, CytomineReader
from shapely.geometry import Polygon


class Filter(object):
    def __init__(self):
        return

    def process(self, image):
        raise NotImplementedError("Should have implemented this")


class AdaptiveThresholdFilter(Filter):
    def __init__(self, block_size=71, c=3):
        super(Filter, self).__init__()
        self.block_size = block_size
        self.c = c

    def process(self, image):
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image_gray = cv2.adaptiveThreshold(image_gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,
                                           self.block_size, self.c)
        return image_gray


class BinaryFilter(Filter):
    def __init__(self, threshold=128):
        super(Filter, self).__init__()
        self.threshold = threshold

    def process(self, image):
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image_gray = cv2.threshold(image_gray, self.threshold, 255, cv2.THRESH_BINARY_INV)
        return image_gray


class OtsuFilter(Filter):
    def __init__(self, threshold=128):
        super(Filter, self).__init__()
        self.threshold = threshold

    def process(self, image):
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image_gray = cv2.threshold(image_gray, self.threshold, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        return image_gray

    
def main(argv):

    base_path = os.getenv("HOME") # Mandatory for Singularity

    #Available filters
    filters = {'binary' : BinaryFilter(), 'adaptive' : AdaptiveThresholdFilter(), 'otsu' : OtsuFilter()}

    with CytomineJob.from_cli(argv) as cj:
        cj.job.update(status=Job.RUNNING, progress=0, statusComment="Initialization...")

        working_path = os.path.join(base_path, "data", str(cj.job.id))
        
        filter = filters.get(cj.parameters.cytomine_filter)
        
        images = ImageInstanceCollection().fetch_with_filter("project", cj.parameters.cytomine_id_project)
        whole_slide = WholeSlide(conn.get_image_instance(parameters['cytomine_id_image'], True))

        async = False #True is experimental
        reader = CytomineReader(conn, whole_slide, window_position = Bounds(0,0, cj.parameters.cytomine_tile_size, cj.parameters.cytomine_tile_size), zoom = cj.parameters.cytomine_zoom_level, overlap = cj.parameters.cytomine_tile_overlap)
        reader.window_position = Bounds(0, 0, reader.window_position.width, reader.window_position.height)


        #Browse the slide using reader
        i = 0
        geometries = []
        cj.job.update(progress=0, status_comment="Browsing big image...")

        while True:
            #Read next tile
            reader.read(async = async)
            image=reader.data
            #Saving tile image locally
            tile_filename = "%s/image-%d-zoom-%d-tile-%d-x-%d-y-%d.png" %(working_path,
                                                                          cj.parameters.cytomine_id_image,
                                                                          cj.parameters.cytomine_zoom_level,
                                                                          i,
                                                                          reader.window_position.x,
                                                                          reader.window_position.y)
            image.save(tile_filename,"PNG")
            #Apply filtering
            cv_image = np.array(reader.result())
            filtered_cv_image = filter.process(cv_image)
            i += 1
            #Detect connected components
            components = ObjectFinder(filtered_cv_image).find_components()
            #Convert local coordinates (from the tile image) to global coordinates (the whole slide)
            components = whole_slide.convert_to_real_coordinates(whole_slide, components, reader.window_position, reader.zoom)
            geometries.extend(Utils().get_geometries(components, cj.parameters.cytomine_min_area, cj.parameters.cytomine_max_area))


            annotations = AnnotationCollection()
            #Upload annotations (geometries corresponding to connected components) to Cytomine core
            #Upload each geometry and add predicted term
            for geometry in geometries:
                annotations.append(Annotation(location=geometry,
                                              id_image=cj.parameters.cytomine_id_image,
                                              id_project=cj.parameters.cytomine_id_project,
                                              id_terms=[cj.parameters.cytomine_id_predicted_term]))
                if len(annotations) % 100 == 0:
                    annotations.save()
                    annotations = AnnotationCollection()

            annotations.save()
            geometries = []
            if not reader.next(): break

        cj.job.update(progress=50, status_comment="Detection done, starting Union over whole big image...")

        
        host = cj.parameters.cytomine_host.replace("http://" , "")    
        #Union of geometries (because geometries are computed locally in each time but objects (e.g. cell clusters) might overlap several tiles)
        #        unioncommand = "groovy -cp \"../../lib/jars/*\" ../../lib/union4.groovy http://%s %s %s %d %d %d %d %d %d %d %d %d %d" %(cj.parameters.cytomine_host
        unioncommand = "groovy -cp \"lib/jars/*\" lib/union4.groovy http://%s %s %s %d %d %d %d %d %d %d %d %d %d" %(cj.parameters.cytomine_host,
                                                                                                                                 cj._public_key,cj._private_key, # ????
                                                                                                                                 cj.parameters.cytomine_id_image,
                                                                                                                                 cj.userJob, # ????
                                                                                                                                 cj.parameters.cytomine_id_predicted_term, #union_term
                                                                                                                                 cj.parameters.cytomine_union_min_length, #union_minlength,
                                                                                                                                 cj.parameters.cytomine_union_bufferoverlap, #union_bufferoverlap,
                                                                                                                                 cj.parameters.cytomine_union_min_point_for_simplify, #union_minPointForSimplify,
                                                                                                                                 cj.parameters.cytomine_union_min_point, #union_minPoint,
                                                                                                                                 cj.parameters.cytomine_union_max_point, #union_maxPoint,
                                                                                                                                 cj.parameters.cytomine_union_nb_zones_width, #union_nbzonesWidth,
                                                                                                                                 cj.parameters.cytomine_union_nb_zones_height) #union_nbzonesHeight)

        os.chdir(current_path)
        print(unioncommand)
        os.system(unioncommand)
    
        
    cj.job.update(statusComment="Finished.")
         

if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
