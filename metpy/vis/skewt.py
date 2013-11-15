#Copyright (c) 2008 Ryan May

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection
from matplotlib.ticker import FixedLocator, AutoLocator, ScalarFormatter
import matplotlib.transforms as transforms
import matplotlib.axis as maxis
import matplotlib.artist as artist
from matplotlib.projections import register_projection

import numpy as np

#TODO:
#   *Panning and zooming are horribly broken, probably because the
#    skewed data are used as bounds. Needs to be disabled (especially panning)
#    or updated to work sensibly
#   *How do we automatically pick appropriate limits so that all relevant
#    slanted gridlines are added?
#   *How do we get the labels we want at the top?
#   *Set good aspect ratio, at least by default
#    - set_aspect(1/11.17, adjustable='datalim') would seem to do what I want
#       except that when I resize the figure, there's a lot of jumping around
#       Might be related to panning/zooming problems
#   *New functions/methods needed to add the various significant lines:
#       -Moist adiabats: ThetaE (HOW THE HECK DOES IT WORK?)
#   *Combine skewT plot with separate subplot for vertical wind plot using
#    barbs?

class SkewXTick(maxis.XTick):
    def draw(self, renderer):
        if not self.get_visible(): return
        renderer.open_group(self.__name__)

        if self.gridOn:
            self.gridline.draw(renderer)
        if self.tick1On:
            self.tick1line.draw(renderer)
        if self.tick2On:
            self.tick2line.draw(renderer)

        if self.label1On:
            self.label1.draw(renderer)
        if self.label2On:
            self.label2.draw(renderer)

        renderer.close_group(self.__name__)

    def set_clip_path(self, clippath, transform=None):
        artist.Artist.set_clip_path(self, clippath, transform)
        self.tick1line.set_clip_path(clippath, transform)
        self.tick2line.set_clip_path(clippath, transform)
        self.gridline.set_clip_path(clippath, transform)
    set_clip_path.__doc__ = artist.Artist.set_clip_path.__doc__

class SkewXAxis(maxis.XAxis):
    def _get_tick(self, major):
        return SkewXTick(self.axes, 0, '', major=major)

    def draw(self, renderer, *args, **kwargs):
        'Draw the axis lines, grid lines, tick lines and labels'
        ticklabelBoxes = []
        ticklabelBoxes2 = []

        if not self.get_visible(): return
        renderer.open_group(__name__)
        interval = self.get_view_interval()
        for tick, loc, label in self.iter_ticks():
            if tick is None: continue
            if transforms.interval_contains(interval, loc):
                tick.set_label1(label)
                tick.set_label2(label)
            tick.update_position(loc)
            tick.draw(renderer)
            if tick.label1On and tick.label1.get_visible():
                extent = tick.label1.get_window_extent(renderer)
                ticklabelBoxes.append(extent)
            if tick.label2On and tick.label2.get_visible():
                extent = tick.label2.get_window_extent(renderer)
                ticklabelBoxes2.append(extent)

        # scale up the axis label box to also find the neighbors, not
        # just the tick labels that actually overlap note we need a
        # *copy* of the axis label box because we don't wan't to scale
        # the actual bbox

        self._update_label_position(ticklabelBoxes, ticklabelBoxes2)

        self.label.draw(renderer)

        self._update_offset_text_position(ticklabelBoxes, ticklabelBoxes2)
        self.offsetText.set_text( self.major.formatter.get_offset() )
        self.offsetText.draw(renderer)

class SkewXAxes(Axes):
    # The projection must specify a name.  This will be used be the
    # user to select the projection, i.e. ``subplot(111,
    # projection='skewx')``.
    name = 'skewx'

    def _init_axis(self):
        #Taken from Axes and modified to use our modified X-axis
        "move this out of __init__ because non-separable axes don't use it"
        self.xaxis = SkewXAxis(self)
        self.yaxis = maxis.YAxis(self)
        self._update_transScale()

#    def get_axes_patch(self):
#        """
#        Override this method to define the shape that is used for the
#        background of the plot.  It should be a subclass of Patch.

#        In this case, it is a Circle (that may be warped by the axes
#        transform into an ellipse).  Any data and gridlines will be
#        clipped to this shape.
#        """
#        return Circle((0.5, 0.5), 0.5)

    def draw(self, *args):
        '''
        draw() is overridden here to allow the data transform to be updated
        before calling the Axes.draw() method.  This allows resizes to be
        properly handled without registering callbacks.  The amount of
        work done here is kept to a minimum.
        '''
        self._update_data_transform()
        Axes.draw(self, *args)

    def _update_data_transform(self):
        '''
        This separates out the creating of the data transform so that
        it alone is updated at draw time.
        '''
        # This transforms x in pixel space to be x + the offset in y from
        # the lower left corner - producing an x-axis sloped 45 degrees
        # down, or x-axis grid lines sloped 45 degrees to the right
        self.transProjection.set(transforms.Affine2D(
            np.array([[1, 1, -self.bbox.ymin], [0, 1, 0], [0, 0, 1]])))

        # Full data transform
        self.transData.set(self._transDataNonskew + self.transProjection)

    def _set_lim_and_transforms(self):
        """
        This is called once when the plot is created to set up all the
        transforms for the data, text and grids.
        """
        #Get the standard transform setup from the Axes base class
        Axes._set_lim_and_transforms(self)

        #Save the unskewed data transform for our own use when regenerating
        #the data transform. The user might want this as well
        self._transDataNonskew = self.transData

        #Create a wrapper for the data transform, so that any object that
        #grabs this transform will see an updated version when we change it
        self.transData = transforms.TransformWrapper(
            transforms.IdentityTransform())

        #Create a wrapper for the proj. transform, so that any object that
        #grabs this transform will see an updated version when we change it
        self.transProjection = transforms.TransformWrapper(
            transforms.IdentityTransform())
        self._update_data_transform()

    def get_xaxis_transform(self, which='grid'):
        """
        Get the transformation used for drawing x-axis labels, ticks
        and gridlines.  The x-direction is in data coordinates and the
        y-direction is in axis coordinates.

        We override here so that the x-axis gridlines get properly
        transformed for the skewed plot.
        """
        return self._xaxis_transform + self.transProjection

    # Disable panning until we find a way to handle the problem with
    # the projection
    def start_pan(self, x, y, button):
        pass

    def end_pan(self):
        pass

    def drag_pan(self, button, key, x, y):
        pass

# Now register the projection with matplotlib so the user can select
# it.
register_projection(SkewXAxes)


def moist_lapserate(w, T):
    # From AMS glossary,
    # http://glossary.ametsoc.org/wiki/Moist-adiabatic_lapse_rate

    # the constants are hardcoded to match consts in plot_skewt - 
    # probably this ought to be refactored to group all atmo 
    # related consts into one common location

    # copied from Wallace & Hobbs 2nd edition, page 467,468
    g = 9.81
    Cp = 1004
    Rd = 287.0
    Rv = 461.51
    epsilon = Rd/Rv
    T0 = 273.15

    # assumes T is in deg C; this is a linear interp/extrap from:
    # Lv = 2.5e6 (O deg C) and 2.0e6 (100 deg C)
    Lv_func = lambda T: 2.5e6 - 2500.0 * T
    # alternate form (Glanz and Orlob 1973, 
    # B. Henderson-Sellers 1984 QJRMS
    #Lv_func = lambda T: 1.91846e6 * ((T+T0)/(T+T0-33.91))**2

    TK = T + T0
    Lv = Lv_func(T)
    A = Lv * w / (Rd*TK)
    return g * (1 + A) / (Cp + Lv * epsilon * A / TK)

def moist_pseudo_lapserate(w, T):
    # From AMS glossary,
    # http://glossary.ametsoc.org/wiki/Pseudoadiabatic_lapse_rate

    # the constants are hardcoded to match consts in plot_skewt - 
    # probably this ought to be refactored to group all atmo 
    # related consts into one common location

    # copied from Wallace & Hobbs 2nd edition, page 467,468
    g = 9.81
    Cp = 1004
    Cv = 717
    Rd = 287.0
    Rv = 461.51
    epsilon = Rd/Rv
    T0 = 273.15

    # assumes T is in deg C; this is a linear interp/extrap from:
    # Lv = 2.5e6 (O deg C) and 2.0e6 (100 deg C)
    Lv_func = lambda T: 2.5e6 - 2500.0 * T
    # alternate form (Glanz and Orlob 1973, 
    # B. Henderson-Sellers 1984 QJRMS)
    #Lv_func = lambda T: 1.91846e6 * (T/(T-33.91))**2

    TK = T + T0
    Lv = Lv_func(T)
    A = Lv * w / (Rd*TK)
    return g * ( (1 + w) * (1 + A) / 
                 (Cp + w*Cv + Lv * (epsilon + w) * A / TK) )


def calc_moist_adiabat(Tref, P):

    # the constants are hardcoded to match consts in plot_skewt - 
    # probably this ought to be refactored to group all atmo 
    # related consts into one common location

    # copied from Wallace & Hobbs 2nd edition, page 467,468
    g = 9.81
    Cp = 1004
    Rd = 287.0
    Rv = 461.51
    epsilon = Rd/Rv
    T0 = 273.15

    T = np.zeros(P.shape)
    T[0] = Tref
    # want "upward" P - e.g. P should be decreasing. Assume it is monotonic 
    # and flip it if needed.
    if P[0]<P[1]:
        uP = P[::-1]
    else:
        uP = P
    dP = uP[:-1] - uP[1:]

    for n in range(1,P.shape[0]):
        # First, find the thickness, in m, of the layer with pressure 
        # thickess given by dP, but assuming the T and wv pressure from 
        # the level at the bottom of the layer.

        # using same approx as used below in plot_skewt() to plot the mixing 
        # ratio lines (though I am unsure of the source)
        # May want to modify to use the MK approximation.
        wv_sat = 6.112 * np.exp(17.67 * T[n-1] / (243.5 + T[n-1]))
        # wv_sat = wv_satpressure_mk(T[n-1])

        # Following Wallace & Hobbs, page 80, 2nd ed.
        # find mixing ratio from dewpoint and then virtual temp
        w = epsilon * wv_sat / (uP[n-1] - wv_sat)
        Tv = (T[n-1] + T0) * (1 + ((1-epsilon)/epsilon) * w)
        rho = uP[n-1] / (Rd * Tv)
        Dz = dP[n-1] / rho / g

        # second, compute the lapse rate, and then combine with the 
        # thickess to get the temperate at the level at the top of the layer.
        Gamma = moist_lapserate(w, T[n-1])
        T[n] = T[n-1] - Gamma * Dz

        # Now that we have the temp at layer top, repeat calculation at midpt, 
        # using the average layer temp (I think this is slightly more correct)
        Tbar = 0.5*(T[n-1] + T[n])
        Pbar = 0.5*(uP[n-1] + uP[n])
        wv_sat = 6.112 * np.exp(17.67 * Tbar / (243.5 + Tbar))
        w = epsilon * wv_sat / (Pbar - wv_sat)
        Tv = (Tbar + T0) * (1 + ((1-epsilon)/epsilon) * w)
        rho = Pbar / (Rd * Tv)
        Dz = dP[n-1] / rho / g
        Gamma = moist_lapserate(w, Tbar)
        T[n] = T[n-1] - Gamma * Dz

    return T

def wv_satpressure_mk(T):
    """ es = wv_satpressure_mk(T):
    Compute saturation vapor pressure, with respect to liquid water. The 
    result is given in hPa, from an input temperature in degrees C. This 
    approximation is valid for typical atmospheric temperatures.
    
    Uses formula from Murphy and Koop, 2005, 
    Q. J. Royal Met. Soc. 131, 1539-1565.
    As suggested by http://cires.colorado.edu/~voemel/vp.html

    """

    TK = T + 273.15
    log_es = 54.842763 - 6763.22/TK - 4.21*np.log(TK) + 0.000367*TK + \
        np.tanh(0.0415*(TK-218.8)) * \
        (53.878 - 1331.22/TK - 9.44523*np.log(TK) + 0.014025*TK)
    # M&K equation returns [Pa], so convert to [hPa]
    es = np.exp(log_es) / 100;
    return es

def plot_skewt(p,h,T,Td, fig=None, ax=None, **kwargs):
    import matplotlib.pyplot as plt

    if fig is None:
        fig = plt.figure(1, figsize=(6.5875, 6.2125))
        fig.clf()
    if ax is None:
        ax = fig.add_subplot(111, projection='skewx')

    plt.grid(True)

#     print "T"
#     print T
#     print "Td"
#     print Td
#     print "p"
#     print p

    ax.semilogy(T, p, 'r')
    ax.semilogy(Td, p, 'g')

    ax.set_yticks(np.linspace(100,1000,10))
    ax.yaxis.set_major_formatter(ScalarFormatter())
    ax.set_xticks(np.arange(-80,45,10))
    ax.set_xlim(-40,45)
    ax.set_ylim(1050,50)

    T0 = ax.get_xticks()

    # allowing P0 to be redefined causes headaches for the moist 
    # adiabats, so don't allow it.
    P0 = 1000.
    R = kwargs.get('R', 287.05)
    Cp = kwargs.get('Cp', 1004.)

    # easier if we start at 1000 and just add the 1050 (see discussion 
    # below with moist adiabats)
    # Note this re-hardcodes the ylimit which is not so great.
    P = np.r_[1050, np.linspace(1000, 50)]
    P = P.reshape(1, -1)

    # I think it makes more sense to plot starting from xticks and then 
    # extrapolate to a wider range with the same tick increment size
    DT = T0[1]-T0[0]
    adiabat_Ts = np.r_[T0, T0[-1] + np.arange(1,10)*DT]
    T = (adiabat_Ts[:,np.newaxis] + 273.15) * (P/P0)**(R/Cp) - 273.15
    linedata = [np.vstack((t[np.newaxis,:], P)).T for t in T]
    dry_adiabats = LineCollection(linedata, colors='r', linestyles='dashed',
                                  alpha=0.5)
    ax.add_collection(dry_adiabats)

    # add moist adiabats
    # Now, we need T to be equal to the ticks (T0) at P=1000 
    # (the reference pressure). So, the trick here is to do it in 
    # two steps (integrate up from P=1000 to top of profile) and 
    # once downward (from P = 1000 to 1050). For the downward, compute 
    # lapse rate at 1000 and assume it is linear in that segment.
    P1000 = np.array([1001.0, 1000.0])
    # also don't need as many T's here (the moist will move off the right 
    # edge of the plot pretty quickly)
    adiabat_Ts = np.r_[T0, T0[-1] + np.arange(1,3)*DT]
    T = np.zeros( (adiabat_Ts.shape[0], P.shape[1]) )
    for n in range(adiabat_Ts.shape[0]):
        T[n,1:] = calc_moist_adiabat(adiabat_Ts[n], P[0,1:])
        tmpT = calc_moist_adiabat(adiabat_Ts[n], P1000)
        T[n,0] = T[n,1] + (tmpT[0]-tmpT[1]) * 50.0

    linedata = [np.vstack((t[np.newaxis,:], P)).T for t in T]
    moist_adiabats = LineCollection(linedata, colors='r', 
                                    linestyles='dotted', alpha=0.5)
    ax.add_collection(moist_adiabats)

    w = np.array([0.0004,0.001, 0.002, 0.004, 0.007, 0.01, 0.016, 0.024,
        0.032]).reshape(-1, 1)
    e = P * w / (0.622 + w)
    T = 243.5/(17.67/np.log(e/6.112) - 1)
    linedata = [np.vstack((t[np.newaxis,:], P)).T for t in T]
    mixing = LineCollection(linedata, colors='g', linestyles='dashed',
        alpha=0.8)
    ax.add_collection(mixing)
    
    return fig, ax


if __name__ == '__main__':
    # Now make a simple example using the custom projection.
    import matplotlib.pyplot as plt
    from StringIO import StringIO

    #Some examples data
    data_txt = '''
  978.0    345    7.8    0.8     61   4.16    325     14  282.7  294.6  283.4
  971.0    404    7.2    0.2     61   4.01    327     17  282.7  294.2  283.4
  946.7    610    5.2   -1.8     61   3.56    335     26  282.8  293.0  283.4
  944.0    634    5.0   -2.0     61   3.51    336     27  282.8  292.9  283.4
  925.0    798    3.4   -2.6     65   3.43    340     32  282.8  292.7  283.4
  911.8    914    2.4   -2.7     69   3.46    345     37  282.9  292.9  283.5
  906.0    966    2.0   -2.7     71   3.47    348     39  283.0  293.0  283.6
  877.9   1219    0.4   -3.2     77   3.46      0     48  283.9  293.9  284.5
  850.0   1478   -1.3   -3.7     84   3.44      0     47  284.8  294.8  285.4
  841.0   1563   -1.9   -3.8     87   3.45    358     45  285.0  295.0  285.6
  823.0   1736    1.4   -0.7     86   4.44    353     42  290.3  303.3  291.0
  813.6   1829    4.5    1.2     80   5.17    350     40  294.5  309.8  295.4
  809.0   1875    6.0    2.2     77   5.57    347     39  296.6  313.2  297.6
  798.0   1988    7.4   -0.6     57   4.61    340     35  299.2  313.3  300.1
  791.0   2061    7.6   -1.4     53   4.39    335     33  300.2  313.6  301.0
  783.9   2134    7.0   -1.7     54   4.32    330     31  300.4  313.6  301.2
  755.1   2438    4.8   -3.1     57   4.06    300     24  301.2  313.7  301.9
  727.3   2743    2.5   -4.4     60   3.81    285     29  301.9  313.8  302.6
  700.5   3048    0.2   -5.8     64   3.57    275     31  302.7  313.8  303.3
  700.0   3054    0.2   -5.8     64   3.56    280     31  302.7  313.8  303.3
  698.0   3077    0.0   -6.0     64   3.52    280     31  302.7  313.7  303.4
  687.0   3204   -0.1   -7.1     59   3.28    281     31  304.0  314.3  304.6
  648.9   3658   -3.2  -10.9     55   2.59    285     30  305.5  313.8  305.9
  631.0   3881   -4.7  -12.7     54   2.29    289     33  306.2  313.6  306.6
  600.7   4267   -6.4  -16.7     44   1.73    295     39  308.6  314.3  308.9
  592.0   4381   -6.9  -17.9     41   1.59    297     41  309.3  314.6  309.6
  577.6   4572   -8.1  -19.6     39   1.41    300     44  310.1  314.9  310.3
  555.3   4877  -10.0  -22.3     36   1.16    295     39  311.3  315.3  311.5
  536.0   5151  -11.7  -24.7     33   0.97    304     39  312.4  315.8  312.6
  533.8   5182  -11.9  -25.0     33   0.95    305     39  312.5  315.8  312.7
  500.0   5680  -15.9  -29.9     29   0.64    290     44  313.6  315.9  313.7
  472.3   6096  -19.7  -33.4     28   0.49    285     46  314.1  315.8  314.1
  453.0   6401  -22.4  -36.0     28   0.39    300     50  314.4  315.8  314.4
  400.0   7310  -30.7  -43.7     27   0.20    285     44  315.0  315.8  315.0
  399.7   7315  -30.8  -43.8     27   0.20    285     44  315.0  315.8  315.0
  387.0   7543  -33.1  -46.1     26   0.16    281     47  314.9  315.5  314.9
  382.7   7620  -33.8  -46.8     26   0.15    280     48  315.0  315.6  315.0
  342.0   8398  -40.5  -53.5     23   0.08    293     52  316.1  316.4  316.1
  320.4   8839  -43.7  -56.7     22   0.06    300     54  317.6  317.8  317.6
  318.0   8890  -44.1  -57.1     22   0.05    301     55  317.8  318.0  317.8
  310.0   9060  -44.7  -58.7     19   0.04    304     61  319.2  319.4  319.2
  306.1   9144  -43.9  -57.9     20   0.05    305     63  321.5  321.7  321.5
  305.0   9169  -43.7  -57.7     20   0.05    303     63  322.1  322.4  322.1
  300.0   9280  -43.5  -57.5     20   0.05    295     64  323.9  324.2  323.9
  292.0   9462  -43.7  -58.7     17   0.05    293     67  326.2  326.4  326.2
  276.0   9838  -47.1  -62.1     16   0.03    290     74  326.6  326.7  326.6
  264.0  10132  -47.5  -62.5     16   0.03    288     79  330.1  330.3  330.1
  251.0  10464  -49.7  -64.7     16   0.03    285     85  331.7  331.8  331.7
  250.0  10490  -49.7  -64.7     16   0.03    285     85  332.1  332.2  332.1
  247.0  10569  -48.7  -63.7     16   0.03    283     88  334.7  334.8  334.7
  244.0  10649  -48.9  -63.9     16   0.03    280     91  335.6  335.7  335.6
  243.3  10668  -48.9  -63.9     16   0.03    280     91  335.8  335.9  335.8
  220.0  11327  -50.3  -65.3     15   0.03    280     85  343.5  343.6  343.5
  212.0  11569  -50.5  -65.5     15   0.03    280     83  346.8  346.9  346.8
  210.0  11631  -49.7  -64.7     16   0.03    280     83  349.0  349.1  349.0
  200.0  11950  -49.9  -64.9     15   0.03    280     80  353.6  353.7  353.6
  194.0  12149  -49.9  -64.9     15   0.03    279     78  356.7  356.8  356.7
  183.0  12529  -51.3  -66.3     15   0.03    278     75  360.4  360.5  360.4
  164.0  13233  -55.3  -68.3     18   0.02    277     69  365.2  365.3  365.2
  152.0  13716  -56.5  -69.5     18   0.02    275     65  371.1  371.2  371.1
  150.0  13800  -57.1  -70.1     18   0.02    275     64  371.5  371.6  371.5
  136.0  14414  -60.5  -72.5     19   0.02    268     54  376.0  376.1  376.0
  132.0  14600  -60.1  -72.1     19   0.02    265     51  380.0  380.1  380.0
  131.4  14630  -60.2  -72.2     19   0.02    265     51  380.3  380.4  380.3
  128.0  14792  -60.9  -72.9     19   0.02    266     50  381.9  382.0  381.9
  125.0  14939  -60.1  -72.1     19   0.02    268     49  385.9  386.0  385.9
  119.0  15240  -62.2  -73.8     20   0.01    270     48  387.4  387.5  387.4
  112.0  15616  -64.9  -75.9     21   0.01    265     53  389.3  389.3  389.3
  108.0  15838  -64.1  -75.1     21   0.01    265     58  394.8  394.9  394.8
  107.8  15850  -64.1  -75.1     21   0.01    265     58  395.0  395.1  395.0
  105.0  16010  -64.7  -75.7     21   0.01    272     50  396.9  396.9  396.9
  103.0  16128  -62.9  -73.9     21   0.02    277     45  402.5  402.6  402.5
  100.0  16310  -62.5  -73.5     21   0.02    285     36  406.7  406.8  406.7
   97.7  16454  -60.5  -72.5     19   0.02    274     30  413.3  413.4  413.3
   92.9  16764  -61.5  -73.1     20   0.02    250     17  417.4  417.5  417.4
   88.4  17069  -62.4  -73.6     21   0.02    225     30  421.5  421.6  421.5
   80.0  17678  -64.3  -74.7     23   0.02    260     35  429.7  429.8  429.7
   76.2  17983  -65.3  -75.3     24   0.02    240     29  433.8  433.9  433.8
   76.0  17997  -65.3  -75.3     24   0.02    240     29  434.0  434.1  434.0
   72.5  18288  -63.6  -74.3     22   0.02    240     24  443.6  443.8  443.6
   71.1  18404  -62.9  -73.9     21   0.02    237     20  447.5  447.6  447.5
   70.0  18500  -62.9  -73.9     21   0.02    235     16  449.5  449.6  449.5
   69.0  18593  -63.2  -74.1     22   0.02    230     16  450.7  450.9  450.7
   62.4  19202  -65.5  -75.7     23   0.02    225      2  458.7  458.9  458.7
   60.7  19375  -66.1  -76.1     23   0.02    195      5  461.0  461.2  461.0
   56.5  19812  -64.4  -75.4     21   0.02    120     12  474.3  474.5  474.4
   56.2  19846  -64.3  -75.3     21   0.02    119     12  475.4  475.6  475.4
   53.0  20205  -66.3  -76.3     23   0.02    114     16  478.8  478.9  478.8
   51.1  20422  -65.7  -75.7     24   0.03    110     18  485.1  485.3  485.1
   50.0  20560  -65.3  -75.3     24   0.03                489.2  489.4  489.2
   49.8  20584  -65.5  -75.5     24   0.03                489.3  489.5  489.3
   48.7  20721  -63.1  -74.1     21   0.03                498.1  498.3  498.1'''

    sound_data = StringIO(data_txt)
    p,h,T,Td = np.loadtxt(sound_data, usecols=range(0,4), unpack=True)

    fig, ax = plot_skewt(p,h,T,Td)

#    Lv = 2.4e6
#    T = T[:,0][:,np.newaxis] * (P/P0)**(R/Cp) - (Lv/Cp) * w
#    linedata = [np.vstack((t[np.newaxis,:], P)).T for t in T]
#    moist_adiabat = LineCollection(linedata, colors='b', linestyles='dashed',
#        alpha=0.8)
#    ax.add_collection(moist_adiabat)

    plt.draw()
    plt.show()
