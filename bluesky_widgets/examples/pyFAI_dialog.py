"""
This file is vendored from pyFAI.app.calib2.

It has been modified to hook in bluesky_widgets' search functionality, available
from a new menu item in the top menu bar.

The changes are marked below with comments.
"""
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Project: Azimuthal integration
#             https://github.com/silx-kit/pyFAI
#
#    Copyright (C) 2017-2018 European Synchrotron Radiation Facility, Grenoble, France
#
#    Principal author:       Jérôme Kieffer (Jerome.Kieffer@ESRF.eu)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""GUI tool for determining the geometry of a detector using a reference sample."""

__author__ = "Valentin Valls"
__contact__ = "valentin.valls@esrf.eu"
__license__ = "MIT"
__copyright__ = "European Synchrotron Radiation Facility, Grenoble, France"
__date__ = "21/01/2020"
__status__ = "production"

import os
import sys
import datetime
from argparse import ArgumentParser

import logging

logging.basicConfig(level=logging.INFO)
logging.captureWarnings(True)
logger = logging.getLogger(__name__)
try:
    import hdf5plugin  # noqa
except ImportError:
    logger.debug("Unable to load hdf5plugin, backtrace:", exc_info=True)

logger_uncaught = logging.getLogger("pyFAI-calib2.UNCAUGHT")

import pyFAI.resources
import pyFAI.calibrant
import pyFAI.detectors
import pyFAI.io.image
from pyFAI.io.ponifile import PoniFile

try:
    from rfoo.utils import rconsole

    rconsole.spawn_server()
except ImportError:
    logger.debug("No socket opened for debugging. Please install rfoo")


def configure_parser_arguments(parser):
    # From AbstractCalibration

    parser.add_argument("args", metavar="FILE", help="List of files to calibrate", nargs="*")

    # Not yet used
    parser.add_argument(
        "-o",
        "--out",
        dest="outfile",
        help="Filename where processed image is saved",
        metavar="FILE",
        default=None,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="debug",
        action="store_true",
        default=False,
        help="switch to debug/verbose mode",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        default=False,
        help="Set logging system in debug mode",
    )
    parser.add_argument(
        "--opengl",
        "--gl",
        dest="opengl",
        action="store_true",
        default=False,
        help="Enable OpenGL rendering (else matplotlib is used)",
    )

    # Settings
    parser.add_argument(
        "-c",
        "--calibrant",
        dest="spacing",
        metavar="FILE",
        help="Calibrant name or file containing d-spacing of the reference sample (case sensitive)",
        default=None,
    )
    parser.add_argument(
        "-w",
        "--wavelength",
        dest="wavelength",
        type=float,
        help="wavelength of the X-Ray beam in Angstrom.",
        default=None,
    )
    parser.add_argument(
        "-e",
        "--energy",
        dest="energy",
        type=float,
        help="energy of the X-Ray beam in keV (hc=%skeV.A)." % pyFAI.units.hc,
        default=None,
    )
    parser.add_argument(
        "-P",
        "--polarization",
        dest="polarization_factor",
        type=float,
        default=None,
        help="polarization factor, from -1 (vertical) to +1 (horizontal),"
        + " default is None (no correction), synchrotrons are around 0.95",
    )
    parser.add_argument(
        "-D",
        "--detector",
        dest="detector_name",
        help="Detector name (instead of pixel size+spline)",
        default=None,
    )
    parser.add_argument(
        "-m",
        "--mask",
        dest="mask",
        help="file containing the mask (for image reconstruction)",
        default=None,
    )
    parser.add_argument("-p", "--pixel", dest="pixel", help="size of the pixel in micron", default=None)
    parser.add_argument(
        "-s",
        "--spline",
        dest="spline",
        help="spline file describing the detector distortion",
        default=None,
    )

    parser.add_argument(
        "-n",
        "--pt",
        dest="npt",
        help="file with datapoints saved. Example: basename.npt",
        default=None,
    )

    # Not yet used
    parser.add_argument(
        "-i",
        "--poni",
        dest="poni",
        metavar="FILE",
        help="file containing the diffraction parameter (poni-file) [not used].",
        default=None,
    )
    # Not yet used
    parser.add_argument(
        "-b",
        "--background",
        dest="background",
        help="Automatic background subtraction if no value are provided [not used]",
        default=None,
    )
    # Not yet used
    parser.add_argument(
        "-d",
        "--dark",
        dest="dark",
        help="list of comma separated dark images to average and subtract [not used]",
        default=None,
    )
    # Not yet used
    parser.add_argument(
        "-f",
        "--flat",
        dest="flat",
        help="list of comma separated flat images to average and divide [not used]",
        default=None,
    )
    # Not yet used
    parser.add_argument(
        "--filter",
        dest="filter",
        help="select the filter, either mean(default), max or median [not used]",
        default=None,
    )

    # Geometry
    parser.add_argument(
        "-l",
        "--distance",
        dest="dist_mm",
        type=float,
        help="sample-detector distance in millimeter. Default: 100mm",
        default=None,
    )
    parser.add_argument(
        "--dist",
        dest="dist",
        type=float,
        help="sample-detector distance in meter. Default: 0.1m",
        default=None,
    )
    parser.add_argument(
        "--poni1",
        dest="poni1",
        type=float,
        help="poni1 coordinate in meter. Default: center of detector",
        default=None,
    )
    parser.add_argument(
        "--poni2",
        dest="poni2",
        type=float,
        help="poni2 coordinate in meter. Default: center of detector",
        default=None,
    )
    parser.add_argument(
        "--rot1",
        dest="rot1",
        type=float,
        help="rot1 in radians. default: 0",
        default=None,
    )
    parser.add_argument(
        "--rot2",
        dest="rot2",
        type=float,
        help="rot2 in radians. default: 0",
        default=None,
    )
    parser.add_argument(
        "--rot3",
        dest="rot3",
        type=float,
        help="rot3 in radians. default: 0",
        default=None,
    )
    # Constraints
    parser.add_argument(
        "--fix-wavelength",
        dest="fix_wavelength",
        help="fix the wavelength parameter. Default: Activated",
        default=True,
        action="store_true",
    )
    parser.add_argument(
        "--free-wavelength",
        dest="fix_wavelength",
        help="free the wavelength parameter. Default: Deactivated ",
        default=True,
        action="store_false",
    )
    parser.add_argument(
        "--fix-dist",
        dest="fix_dist",
        help="fix the distance parameter",
        default=None,
        action="store_true",
    )
    parser.add_argument(
        "--free-dist",
        dest="fix_dist",
        help="free the distance parameter. Default: Activated",
        default=None,
        action="store_false",
    )
    parser.add_argument(
        "--fix-poni1",
        dest="fix_poni1",
        help="fix the poni1 parameter",
        default=None,
        action="store_true",
    )
    parser.add_argument(
        "--free-poni1",
        dest="fix_poni1",
        help="free the poni1 parameter. Default: Activated",
        default=None,
        action="store_false",
    )
    parser.add_argument(
        "--fix-poni2",
        dest="fix_poni2",
        help="fix the poni2 parameter",
        default=None,
        action="store_true",
    )
    parser.add_argument(
        "--free-poni2",
        dest="fix_poni2",
        help="free the poni2 parameter. Default: Activated",
        default=None,
        action="store_false",
    )
    parser.add_argument(
        "--fix-rot1",
        dest="fix_rot1",
        help="fix the rot1 parameter",
        default=None,
        action="store_true",
    )
    parser.add_argument(
        "--free-rot1",
        dest="fix_rot1",
        help="free the rot1 parameter. Default: Activated",
        default=None,
        action="store_false",
    )
    parser.add_argument(
        "--fix-rot2",
        dest="fix_rot2",
        help="fix the rot2 parameter",
        default=None,
        action="store_true",
    )
    parser.add_argument(
        "--free-rot2",
        dest="fix_rot2",
        help="free the rot2 parameter. Default: Activated",
        default=None,
        action="store_false",
    )
    parser.add_argument(
        "--fix-rot3",
        dest="fix_rot3",
        help="fix the rot3 parameter",
        default=None,
        action="store_true",
    )
    parser.add_argument(
        "--free-rot3",
        dest="fix_rot3",
        help="free the rot3 parameter. Default: Activated",
        default=None,
        action="store_false",
    )

    parser.add_argument(
        "--npt",
        dest="npt_1d",
        help="Number of point in 1D integrated pattern, Default: 1024",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--npt-azim",
        dest="npt_2d_azim",
        help="Number of azimuthal sectors in 2D integrated images. Default: 360",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--npt-rad",
        dest="npt_2d_rad",
        help="Number of radial bins in 2D integrated images. Default: 400",
        type=int,
        default=None,
    )

    # Customization
    parser.add_argument(
        "--qtargs",
        dest="qtargs",
        type=str,
        help="Arguments propagated to Qt",
        default=None,
    )

    # Not yet used
    parser.add_argument(
        "--tilt",
        dest="tilt",
        help="Allow initially detector tilt to be refined (rot1, rot2, rot3). Default: Activated",
        default=None,
        action="store_true",
    )
    # Not yet used
    parser.add_argument(
        "--no-tilt",
        dest="tilt",
        help="Deactivated tilt refinement and set all rotation to 0",
        default=None,
        action="store_false",
    )
    # Not yet used
    parser.add_argument(
        "--saturation",
        dest="saturation",
        help="consider all pixel>max*(1-saturation) as saturated and "
        "reconstruct them, default: 0 (deactivated)",
        default=0,
        type=float,
    )
    # Not yet used
    parser.add_argument(
        "--weighted",
        dest="weighted",
        help="weight fit by intensity, by default not.",
        default=False,
        action="store_true",
    )
    # Not yet used
    parser.add_argument(
        "--unit",
        dest="unit",
        help="Valid units for radial range: 2th_deg, 2th_rad, q_nm^-1," " q_A^-1, r_mm. Default: 2th_deg",
        type=str,
        default="2th_deg",
    )
    # Not yet used
    parser.add_argument(
        "--no-gui",
        dest="gui",
        help="force the program to run without a Graphical interface",
        default=True,
        action="store_false",
    )
    # Not yet used
    parser.add_argument(
        "--no-interactive",
        dest="interactive",
        help="force the program to run and exit without prompting" " for refinements",
        default=True,
        action="store_false",
    )

    # From Calibration
    # Not yet used
    parser.add_argument(
        "-r",
        "--reconstruct",
        dest="reconstruct",
        help="Reconstruct image where data are masked or <0  (for Pilatus "
        + "detectors or detectors with modules)",
        action="store_true",
        default=False,
    )
    # Not yet used
    parser.add_argument(
        "-g",
        "--gaussian",
        dest="gaussian",
        help="""Size of the gaussian kernel.
Size of the gap (in pixels) between two consecutive rings, by default 100
Increase the value if the arc is not complete;
decrease the value if arcs are mixed together.""",
        default=None,
    )
    # Not yet used
    parser.add_argument(
        "--square",
        dest="square",
        action="store_true",
        help="Use square kernel shape for neighbor search instead of diamond shape",
        default=False,
    )


description = """Calibrate the diffraction setup geometry based on
Debye-Sherrer rings images without a priori knowledge of your setup.
You will need to provide a calibrant or a "d-spacing" file containing the
spacing of Miller plans in Angstrom (in decreasing order).
%s or search in the American Mineralogist database:
http://rruff.geo.arizona.edu/AMS/amcsd.php""" % str(
    pyFAI.calibrant.ALL_CALIBRANTS
)

epilog = """The output of this program is a "PONI" file containing the
detector description and the 6 refined parameters (distance, center, rotation)
and wavelength. An 1D and 2D diffraction patterns are also produced.
(.dat and .azim files)"""


def parse_pixel_size(pixel_size):
    """Convert a comma separated sting into pixel size

    :param str pixel_size: String containing pixel size in micron
    :rtype: Tuple[float,float]
    :returns: Returns floating point pixel size in meter
    """
    sp = pixel_size.split(",")
    if len(sp) >= 2:
        try:
            result = [float(i) * 1e-6 for i in sp[:2]]
        except Exception:
            logger.error("Error in reading pixel size_2")
            raise ValueError("Not a valid pixel size")
    elif len(sp) == 1:
        px = sp[0]
        try:
            result = [float(px) * 1e-6, float(px) * 1e-6]
        except Exception:
            logger.error("Error in reading pixel size_1")
            raise ValueError("Not a valid pixel size")
    else:
        logger.error("Error in reading pixel size_0")
        raise ValueError("Not a valid pixel size")
    return result


def parse_options():
    """
    Returns parsed command line argument as an `options` object.

    :raises ExitException: In case of the use of `--help` in the comman line
    """
    usage = "pyFAI-calib2 [options] input_image.edf"
    parser = ArgumentParser(usage=usage, description=description, epilog=epilog)
    version = "calibration from pyFAI  version %s: %s" % (pyFAI.version, pyFAI.date)
    parser.add_argument("-V", "--version", action="version", version=version)
    configure_parser_arguments(parser)

    # Analyse aruments and options
    options = parser.parse_args()
    return options


def displayExceptionBox(message, exc_info):
    """
    Display an exception as a MessageBox

    :param str message: A context message
    :param Union[tuple,Exception] exc_info: An exception or the output of
        exc_info.
    """
    from pyFAI.gui.dialog import MessageBox

    MessageBox.exception(None, message, exc_info, logger)


def setup_model(model, options):
    """
    Setup the model using options from the command line.

    :param pyFAI.gui.model.CalibrationModel model: Model of the application
    """
    args = options.args

    # The module must not import the GUI
    from pyFAI.gui.utils import units

    # TODO: This should be removed
    import pyFAI.gui.cli_calibration

    # Settings
    settings = model.experimentSettingsModel()
    if options.spacing:
        calibrant = None
        try:
            if options.spacing in pyFAI.calibrant.CALIBRANT_FACTORY:
                calibrant = pyFAI.calibrant.CALIBRANT_FACTORY(options.spacing)
            elif os.path.isfile(options.spacing):
                calibrant = pyFAI.calibrant.Calibrant(options.spacing)
            else:
                logger.error("No such Calibrant / d-Spacing file: %s", options.spacing)
        except Exception as e:
            calibrant = None
            displayExceptionBox("Error while loading the calibrant", e)
        if calibrant:
            settings.calibrantModel().setCalibrant(calibrant)

    if options.wavelength:
        value = units.convert(options.wavelength, units.Unit.ANGSTROM, units.Unit.METER_WL)
        settings.wavelength().setValue(value)

    if options.energy:
        value = units.convert(options.energy, units.Unit.ENERGY, units.Unit.METER_WL)
        settings.wavelength().setValue(value)

    if options.polarization_factor:
        settings.polarizationFactor(options.polarization_factor)

    if options.detector_name:
        try:
            detector = pyFAI.gui.cli_calibration.get_detector(options.detector_name)
            if options.pixel:
                logger.warning("Detector model already specified. Pixel size argument ignored.")
        except Exception as e:
            detector = None
            displayExceptionBox("Error while loading the detector", e)
    elif options.pixel:
        pixel_size = parse_pixel_size(options.pixel)
        detector = pyFAI.detectors.Detector(pixel1=pixel_size[0], pixel2=pixel_size[0])
    else:
        detector = None

    if options.spline:
        try:
            if detector is None:
                detector = pyFAI.detectors.Detector(splineFile=options.spline)
            elif detector.__class__ is pyFAI.detectors.Detector or detector.HAVE_TAPER:
                detector.set_splineFile(options.spline)
            else:
                logger.warning("Spline file not supported with this kind of detector. Argument ignored.")
        except Exception as e:
            displayExceptionBox("Error while loading the spline file", e)

    geometryFromPoni = None
    if options.poni:
        settings.poniFile().setValue(options.poni)
        settings.poniFile().setSynchronized(True)

        if os.path.exists(options.poni):
            if detector is None:
                poniFile = PoniFile()
                poniFile.read_from_file(options.poni)
                detector = poniFile.detector

                from pyFAI.gui.model.GeometryModel import GeometryModel

                geometryFromPoni = GeometryModel()
                geometryFromPoni.distance().setValue(poniFile.dist)
                geometryFromPoni.poni1().setValue(poniFile.poni1)
                geometryFromPoni.poni2().setValue(poniFile.poni2)
                geometryFromPoni.rotation1().setValue(poniFile.rot1)
                geometryFromPoni.rotation2().setValue(poniFile.rot2)
                geometryFromPoni.rotation3().setValue(poniFile.rot3)
                geometryFromPoni.wavelength().setValue(poniFile.wavelength)

                geometryHistory = model.geometryHistoryModel()
                now = datetime.datetime.now()
                geometryHistory.appendGeometry("Ponifile", now, geometryFromPoni, None)
            else:
                logger.warning("Detector redefined in the command line. Detector from --poni argument ignored.")
        else:
            logger.warning("PONI file '%s' do not exists. --poni option ignored.", options.poni)

    settings.detectorModel().setDetector(detector)

    if options.mask:
        try:
            with settings.mask().lockContext() as image_model:
                image_model.setFilename(options.mask)
                data = pyFAI.io.image.read_image_data(options.mask)
                image_model.setValue(data)
                image_model.setSynchronized(True)
        except Exception as e:
            displayExceptionBox("Error while loading the mask", e)

    if len(args) == 0:
        pass
    elif len(args) == 1:
        image_file = args[0]
        try:
            with settings.image().lockContext() as image_model:
                image_model.setFilename(image_file)
                data = pyFAI.io.image.read_image_data(image_file)
                image_model.setValue(data)
                image_model.setSynchronized(True)
        except Exception as e:
            displayExceptionBox("Error while loading the image", e)
    else:
        logger.error("Too much images provided. Only one is expected")

    # Geometry
    # FIXME it will not be used cause the fitted geometry will be overwrited
    geometry = model.fittedGeometry()
    if (
        options.dist_mm is not None
        or options.dist is not None
        or options.poni1 is not None
        or options.poni2 is not None
        or options.rot1 is not None
        or options.rot2 is not None
        or options.rot3 is not None
    ):
        if geometryFromPoni is not None:
            logger.warning(
                "Geometry redefined in the command line. Geometry from --poni argument was stored in the history."
            )
        if options.dist_mm is not None:
            geometry.distance().setValue(1e-3 * options.dist_mm)
        if options.dist is not None:
            geometry.distance().setValue(options.dist)
        if options.poni1 is not None:
            geometry.poni1().setValue(options.poni1)
        if options.poni2 is not None:
            geometry.poni2().setValue(options.poni2)
        if options.rot1 is not None:
            geometry.rotation1().setValue(options.rot1)
        if options.rot2 is not None:
            geometry.rotation2().setValue(options.rot2)
        if options.rot3 is not None:
            geometry.rotation3().setValue(options.rot3)
    else:
        if geometryFromPoni is not None:
            geometry.setFrom(geometryFromPoni)

    # Constraints
    constraints = model.geometryConstraintsModel()
    if options.fix_wavelength is not None:
        constraints.wavelength().setFixed(options.fix_wavelength)
    if options.fix_dist is not None:
        constraints.distance().setFixed(options.fix_dist)
    if options.fix_poni1 is not None:
        constraints.poni1().setFixed(options.fix_poni1)
    if options.fix_poni2 is not None:
        constraints.poni2().setFixed(options.fix_poni2)
    if options.fix_rot1 is not None:
        constraints.rotation1().setFixed(options.fix_rot1)
    if options.fix_rot2 is not None:
        constraints.rotation2().setFixed(options.fix_rot2)
    if options.fix_rot3 is not None:
        constraints.rotation3().setFixed(options.fix_rot3)

    integrationSettingsModel = model.integrationSettingsModel()
    npt = None
    if options.npt_1d is not None:
        npt = options.npt_1d
    if options.npt_2d_rad is not None:
        if npt is not None:
            logger.error("Both --npt and --npt-rad defined. The biggest is used.")
            npt = max(npt, options.npt_2d_rad)

    if npt is not None:
        integrationSettingsModel.nPointsRadial().setValue(npt)
    else:
        integrationSettingsModel.nPointsRadial().setValue(1024)

    if options.npt_2d_azim is not None:
        integrationSettingsModel.nPointsAzimuthal().setValue(options.npt_2d_azim)
    else:
        integrationSettingsModel.nPointsAzimuthal().setValue(360)

    # Integration
    if options.unit:
        unit = pyFAI.units.to_unit(options.unit)
        integrationSettingsModel.radialUnit().setValue(unit)

    if options.outfile:
        logger.error("outfile option not supported")

    if options.reconstruct:
        logger.error("reconstruct option not supported")
    if options.gaussian:
        logger.error("gaussian option not supported")
    if options.square:
        logger.error("square option not supported")
    if options.pixel:
        logger.error("pixel option not supported")

    if options.background:
        logger.error("background option not supported")
    if options.dark:
        logger.error("dark option not supported")
    if options.flat:
        logger.error("flat option not supported")
    if options.filter:
        logger.error("filter option not supported")

    if options.tilt:
        logger.error("tilt option not supported")
    if options.saturation:
        logger.error("saturation option not supported")
    if options.weighted:
        logger.error("weighted option not supported")

    if options.gui is not True:
        logger.error("gui option not supported")
    if options.interactive is not True:
        logger.error("interactive option not supported")

    if options.npt:
        try:
            from pyFAI.gui.helper import model_transform
            from pyFAI.control_points import ControlPoints

            controlPoints = ControlPoints(filename=options.npt)
            peakSelectionModel = model.peakSelectionModel()
            model_transform.initPeaksFromControlPoints(peakSelectionModel, controlPoints)
        except Exception as e:
            displayExceptionBox("Error while loading control-point file", e)


def logUncaughtExceptions(exceptionClass, exception, stack):
    try:
        import traceback

        if stack is not None:
            # Mimic the syntax of the default Python exception
            message = "".join(traceback.format_tb(stack))
            message = "{1}\nTraceback (most recent call last):\n{2}{0}: {1}".format(
                exceptionClass.__name__, exception, message
            )
        else:
            # There is no backtrace
            message = "{0}: {1}".format(exceptionClass.__name__, exception)
        logger_uncaught.error(message)
    except Exception:
        # Make sure there is no problem at all in this function
        try:
            logger_uncaught.error(exception)
        except Exception:
            print("Error:" + str(exception))


def main():
    # It have to be done before loading Qt
    # --help must also work without Qt
    options = parse_options()

    if options.debug:
        logging.root.setLevel(logging.DEBUG)

    # Then we can load Qt
    import silx
    from silx.gui import qt

    if options.opengl:
        silx.config.DEFAULT_PLOT_BACKEND = "opengl"

    # Make sure matplotlib is loaded first by silx
    import silx.gui.plot.matplotlib
    from pyFAI.gui.CalibrationWindow import CalibrationWindow
    from pyFAI.gui.CalibrationContext import CalibrationContext

    sys.excepthook = logUncaughtExceptions
    if options.qtargs is None:
        qtArgs = []
    else:
        qtArgs = options.qtargs.split()
    app = qt.QApplication(qtArgs)
    pyFAI.resources.silx_integration()

    settings = qt.QSettings(qt.QSettings.IniFormat, qt.QSettings.UserScope, "pyfai", "pyfai-calib2", None)

    context = CalibrationContext(settings)
    context.restoreSettings()

    setup_model(context.getCalibrationModel(), options)
    window = CalibrationWindow(context)

    # Begin modifications for bluesky_widgets

    from qtpy.QtWidgets import QDialog
    from bluesky_widgets.models.search import Search
    from bluesky_widgets.qt.search import QtSearch
    from bluesky_widgets.examples.utils.generate_msgpack_data import get_catalog
    from bluesky_widgets.examples.utils.add_search_mixin import columns

    from qtpy.QtWidgets import QAction, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

    example_catalog = get_catalog()

    class SearchDialog(QDialog):
        """
        Combine the QtSearches widget with a button that processes selected Runs.
        """

        def __init__(self, model, *args, **kwargs):
            super().__init__(*args, **kwargs)
            layout = QVBoxLayout()
            self.setLayout(layout)
            self.setModal(True)
            layout.addWidget(QtSearch(model))

            accept = QPushButton("Open")
            reject = QPushButton("Cancel")
            # We'll just slip this into an existing widget --- not great form, but
            # this is just a silly example.
            accept.clicked.connect(self.accept)
            reject.clicked.connect(self.reject)
            buttons_widget = QWidget()
            buttons_layout = QHBoxLayout()
            buttons_widget.setLayout(buttons_layout)
            buttons_layout.addWidget(accept)
            buttons_layout.addWidget(reject)
            layout.addWidget(buttons_widget)

    def launch_dialog():
        model = Search(example_catalog, columns=columns)
        dialog = SearchDialog(model)

        def open_catalog():
            catalog = model.selection_as_catalog
            # TODO Extract the data from this.
            print(f"Open {len(catalog)} runs")

        dialog.accepted.connect(open_catalog)
        dialog.exec()

    menu = window.menuBar().addMenu("&Data Broker")
    launch_dialog_action = QAction("&Search")
    menu.addAction(launch_dialog_action)
    launch_dialog_action.triggered.connect(launch_dialog)
    # End modifications for bluesky_widgets

    window.setVisible(True)
    window.setAttribute(qt.Qt.WA_DeleteOnClose, True)

    result = app.exec_()
    context.saveSettings()

    # remove ending warnings relative to QTimer
    app.deleteLater()

    return result


if __name__ == "__main__":
    result = main()
    sys.exit(result)
