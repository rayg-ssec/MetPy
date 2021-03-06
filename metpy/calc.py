'A collection of generic calculation functions.'

__all__ = ['vapor_pressure', 'dewpoint', 'get_speed_dir','get_wind_components',
    'mixing_ratio','tke', 'windchill', 'heat_index', 'h_convergence',
    'v_vorticity', 'convergence_vorticity', 'advection', 'geostrophic_wind']

import numpy as np
from numpy.ma import log, exp, cos, sin, masked_array
from scipy.constants import degree, kilo, hour, g
from metpy.cbook import iterable

sat_pressure_0c = 6.112 # mb
def vapor_pressure(temp):
    '''
    Calculate the saturation water vapor (partial) pressure given
    *temperature*.

    temp : scalar or array
        The temperature in degrees Celsius.

    Returns : scalar or array
        The saturation water vapor (partial) presure in millibars, with
        the same shape as *temp*.

    Instead of temperature, dewpoint may be used in order to calculate
    the actual (ambient) water vapor (partial) pressure.
    '''
    return sat_pressure_0c * exp(17.67 * temp / (temp + 243.5))

def dewpoint(temp, rh):
    '''
    Calculate the ambient dewpoint given air temperature and relative
    humidity.

    temp : scalar or array
        The temperature in degrees Celsius.

    rh : scalar or array
        The relative humidity expressed as a ratio in the range [0, 1]

    Returns : scalar or array
        The dew point temperature in degrees Celsius, with the shape
        of the result being determined using numpy's broadcasting rules.
    '''
    es = vapor_pressure(temp)
    val = log(rh * es/sat_pressure_0c)
    return 243.5 * val / (17.67 - val)

def mixing_ratio(part_press, tot_press):
    '''
    Calculates the mixing ratio of gas given its partial pressure
    and the total pressure of the air.

    part_press : scalar or array
        The partial pressure of the constituent gas.

    tot_press : scalar or array
        The total air pressure.

    Returns : scalar or array
        The (mass) mixing ratio, unitless (e.g. Kg/Kg or g/g)

    There are no required units for the input arrays, other than that
    they have the same units.
    '''
    return part_press / (tot_press - part_press)

def get_speed_dir(u,v,w=None):
    '''
    Compute the wind speed (horizontal and vector is W is supplied) and
    wind direction.

    Return horizontal wind speed, vector wind speed, and wind direction in a tuple
      * if w is not supplied, returns tuple of horizontal wind speed and wind direction.
    '''
    hws = np.sqrt(u*u+v*v)
    wd = np.arctan2(-u,-v)*180./np.pi
    wd[wd<0]=360+wd[wd<0]
    if w is None:
        return hws,wd
    else:
        vws = np.sqrt(u*u+v*v+w*w)
        return hws,vws,wd

def get_wind_components(speed, wdir):
    '''
    Calculate the U, V wind vector components from the speed and
    direction (from which the wind is blowing).

    speed : scalar or array
        The wind speed (magnitude)

    wdir : scalar or array
        The wind direction in degrees

    Returns : tuple of scalars or arrays
        The tuple (U,V) corresponding to the wind components in the
        X (East-West) and Y (North-South) directions, respectively.
    '''
    wdir = wdir * degree
    u = -speed * sin(wdir)
    v = -speed * cos(wdir)
    return u,v

def tke(u,v,w):
    '''
    Compute the turbulence kinetic energy (tke) from the time series of the
    velocity components u, v, and w.

    u : scalar or array
        The wind component along the x-axis

    v : scalar or array
        The wind component along the y-axis

    w : scalar or array
        The wind componennt along the z-axis

    Returns : scalar or array
        The corresponding tke value(s)
    '''
    up = u - u.mean()
    vp = v - v.mean()
    wp = w - w.mean()

    tke = np.power(np.average(np.power(up, 2)) +
                  np.average(np.power(vp, 2)) +
                  np.average(np.power(wp, 2)), 0.5)

    return tke

def windchill(temp, speed, metric=True, face_level_winds=False,
    mask_undefined=True):
    '''
    Calculate the Wind Chill Temperature Index (WCTI) from the current
    temperature and wind speed.

    This implementation comes from the formulas outlined at:
    http://www.ofcm.gov/jagti/r19-ti-plan/pdf/03_chap3.pdf

    Specifically, these formulas assume that wind speed is measured at
    10m.  If, instead, the speeds are measured at face level, the winds
    need to be multiplied by a factor of 1.5 (this can be done by specifying
    *face_level_winds* as True.

    temp : scalar or array
        The air temperature, in Farenheit if *metric* is False or Celsius
        if *metric is True.

    speed : scalar or array
        The wind speed at 10m.  If instead the winds are at face level,
        *face_level_winds* should be set to True and the 1.5 multiplicative
        correction will be applied automatically.  Wind speed should be
        given in units of miles per hour if *metric* is False and
        meters per second if *metric* is True.

    metric : boolean
        A flag indicating whether data is given in metric units. Defaults
        to True.

    face_level_winds : boolean
        A flag indicating whether the wind speeds were measured at facial
        level instead of 10m, thus requiring a correction.  Defaults to
        False.

    mask_undefined : boolean
        A flag indicating whether a masked array should be returned with
        values where wind chill is undefined masked.  These are values where
        the temperature > 50F or wind speed <= 3 miles per hour. Defaults
        to True.

    Returns : scalar or array
        The correspond Wind Chill Temperature Index value(s)
    '''
    # Correct for lower height measurement of winds if necessary
    if face_level_winds:
        speed = speed * 1.5

    if metric:
        # Formula uses wind speed in km/hr, but passing in m/s makes more
        # sense.  Convert here.
        temp_limit, speed_limit = 10., 4.828 #Temp in C, speed in km/h
        speed = speed * hour / kilo
        speed_factor = speed ** 0.16
        wcti = (13.12 + 0.6215 * temp - 11.37 * speed_factor
            + 0.3965 * temp * speed_factor)
    else:
        temp_limit, speed_limit = 50., 3.
        speed_factor = speed ** 0.16
        wcti = (35.74 + 0.6215 * temp - 35.75 * speed_factor
            + 0.4275 * temp * speed_factor)

    #See if we need to mask any undefined values
    if mask_undefined:
        mask = np.array((temp > temp_limit) | (speed <= speed_limit))
        if mask.any():
            wcti = masked_array(wcti, mask=mask)

    return wcti

def heat_index(temp, rh, mask_undefined=True):
    '''
    Calculate the Heat Index from the current temperature and relative
    humidity.

    The implementation uses the formula outlined in:
    http://www.srh.noaa.gov/ffc/html/studies/ta_htindx.PDF

    temp : scalar or array
        The air temperature, in Farenheit.

    rh : scalar or array
        The relative humidity expressed as an integer percentage.

    mask_undefined : boolean
        A flag indicating whether a masked array should be returned with
        values where heat index is undefined masked.  These are values where
        the temperature < 80F or relative humidity < 40 percent. Defaults
        to True.

    Returns : scalar or array
        The corresponding Heat Index value(s)

    Reference:
        Steadman, R.G., 1979: The assessment of sultriness. Part I: A
        temperature-humidity index based on human physiology and clothing
        science. J. Appl. Meteor., 18, 861-873.
    '''
    rh2 = rh**2
    temp2 = temp**2

    # Calculate the Heat Index
    HI = (-42.379 + 2.04901523 * temp + 10.14333127 * rh
        - 0.22475541 * temp * rh - 6.83783e-3 * temp2 - 5.481717e-2 * rh2
        + 1.22874e-3 * temp2 * rh + 8.5282e-4 * temp * rh2
        - 1.99e-6 * temp2 * rh2)

    # See if we need to mask any undefined values
    if mask_undefined:
        mask = np.array((temp < 80.) | (rh < 40))
        if mask.any():
            HI = masked_array(HI, mask=mask)

    return HI

def _get_gradients(u, v, dx, dy):
    #Helper function for getting convergence and vorticity from 2D arrays
    dudx, dudy = np.gradient(u, dx, dy)
    dvdx, dvdy = np.gradient(v, dx, dy)
    return dudx, dudy, dvdx, dvdy

def v_vorticity(u, v, dx, dy):
    '''
    Calculate the vertical vorticity of the horizontal wind.  The grid
    must have a constant spacing in each direction.

    u, v : 2 dimensional arrays
        Arrays with the x and y components of the wind, respectively.
        X must be the first dimension and y the second.

    dx : scalar
        The grid spacing in the x-direction

    dy : scalar
        The grid spacing in the y-direction

    Returns : 2 dimensional array
        The vertical vorticity
    '''
    dudx, dudy, dvdx, dvdy = _get_gradients(u, v, dx, dy)
    return dvdx - dudy

def h_convergence(u, v, dx, dy):
    '''
    Calculate the horizontal convergence of the horizontal wind.  The grid
    must have a constant spacing in each direction.

    u, v : 2 dimensional arrays
        Arrays with the x and y components of the wind, respectively.
        X must be the first dimension and y the second.

    dx : scalar
        The grid spacing in the x-direction

    dy : scalar
        The grid spacing in the y-direction

    Returns : 2 dimensional array
        The horizontal convergence
    '''
    dudx, dudy, dvdx, dvdy = _get_gradients(u, v, dx, dy)
    return dudx + dvdy

def convergence_vorticity(u, v, dx, dy):
    '''
    Calculate the horizontal convergence and vertical vorticity of the
    horizontal wind.  The grid must have a constant spacing in each direction.
    This is a convenience function that will do less work than calculating
    the horizontal convergence and vertical vorticity separately.

    u, v : 2 dimensional arrays
        Arrays with the x and y components of the wind, respectively.
        X must be the first dimension and y the second.

    dx : scalar
        The grid spacing in the x-direction

    dy : scalar
        The grid spacing in the y-direction

    Returns : A 2-item tuple of 2 dimensional arrays
        A tuple of (horizontal convergence, vertical vorticity)
    '''
    dudx, dudy, dvdx, dvdy = _get_gradients(u, v, dx, dy)
    return dudx + dvdy, dvdx - dudy

def advection(scalar, wind, deltas):
    '''
    Calculate the advection of *scalar* by the wind. The order of the
    dimensions of the arrays must match the order in which the wind
    components are given.  For example, if the winds are given [u, v], then
    the scalar and wind arrays must be indexed as x,y (which puts x as the
    rows, not columns).

    scalar : N-dimensional array
        Array (with N-dimensions) with the quantity to be advected.

    wind : sequence of arrays
        Length N sequence of N-dimensional arrays.  Represents the flow,
        with a component of the wind in each dimension.  For example, for
        horizontal advection, this could be a list: [u, v], where u and v
        are each a 2-dimensional array.

    deltas : sequence
        A (length N) sequence containing the grid spacing in each dimension.

    Return : N-dimensional array
        An N-dimensional array containing the advection at all grid points.
    '''
    # Gradient returns a list of derivatives along each dimension.  We convert
    # this to an array with dimension as the first index
    grad = np.asarray(np.gradient(scalar, *deltas))

    # This allows passing in a list of wind components or an array
    wind = np.asarray(wind)

    # Make them be at least 2D (handling the 1D case) so that we can do the
    # multiply and sum below
    grad,wind = np.atleast_2d(grad, wind)

    return (-grad * wind).sum(axis=0)

def geostrophic_wind(heights, f, dx, dy, geopotential=False):
    '''
    Calculate the geostrophic wind given from the heights.  If geopotential
    is set to true, it treats the passed in heights as geopotential and
    will not multiply by g.

    heights : N-dimensional array
        The height field, given with leading dimensions of x by y.  There
        can be trailing dimensions on the array.  If geopotential is False
        (the default), these need to be in units of meters and will be
        multiplied by gravity.  If geopotential is True, no scaling will
        be applied and *heights* should be in units of m^2 s^-s.

    f : scalar or array
        The coriolis parameter in s^-1.  This can be a scalar to be applied
        everywhere or an array of values.

    dx : scalar
        The grid spacing in the x-direction in meters.

    dy : scalar
        The grid spacing in the y-direction in meters.

    Returns : A 2-item tuple of arrays
        A tuple of the x-component and y-component of the geostropic wind in
        m s^-1.
    '''
    if geopotential:
        norm_factor = 1. / f
    else:
        norm_factor = g / f

    # If heights is has more than 2 dimensions, we need to pass in some dummy
    # grid deltas so that we can still use np.gradient.  It may be better to
    # to loop in this case, but that remains to be done.
    deltas = [dx, dy]
    if heights.ndim > 2:
        deltas = deltas + [1.] * (heights.ndim - 2)

    grad = np.gradient(heights, *deltas)
    dx,dy = grad[0], grad[1] # This throws away unused gradient components
    return -norm_factor * dy, norm_factor * dx
