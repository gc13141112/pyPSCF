# -*-coding:Utf-8 -*
import sys, os
import datetime as dt
import numpy as np
import json
import scipy
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
from scipy import signal
import scipy.stats as sst
import math
from multiprocessing import Process
import linecache

# tkinter modules
if sys.version_info.major >= 3:
    from tkinter.messagebox import *
    #sys.exit("You have to run it with python 2, not python 3.")
else:
    # we are on Python 2
    from tkMessageBox import *


class BT(object):
    def __init__(self, global_date=(), conc=0, date=list(), coord=list(), T=list(), rain=list()):
        self.global_date = global_date
        self.conc   = conc
        self.date   = date
        self.coord  = coord
        self.temp   = T
        self.rain   = rain

def makeBT(globaldate, conc, date, coord, T, rain):
    return BT(globaldate, conc, date, coord, T, rain)

def str2date(strdate):
    # "31/10/2010 22:34"
    date=list()
    print(strdate)
    for d in strdate:
        if d=='':
            return float(-999)
        date.append(dt.datetime.strptime(d, '%d/%m/%Y %H:%M'))
    date = np.array(date)
    return(date)

def specie2study(Cfile, sp):
    header=np.genfromtxt(Cfile, delimiter=';', max_rows=1, dtype=str)
    j=-999
    for i in range(0, header.size):
        if header[i].upper()==sp.upper():
            j=i
    return(j)

def dateformat(a):
    if len(a)==1:
        return '0%s' % (a,)
    else:
        return a

def aammddhh(x):
    yy=str(x.year)[2:]
    mm=dateformat(str(x.month))
    dd=dateformat(str(x.day))
    hh=dateformat(str(x.hour))
    return '%s%s%s%s' % (yy,mm,dd,hh)    ##needs to be adapted

def unique2d(a):
    x, y = a
    b = x + y*1.0j
    idx = np.unique(b,return_index=True)[1]
    return a[:,idx]


def arr2json(arr):
    return json.dumps(arr.tolist())
def json2arr(astr,dtype):
    return np.fromiter(json.loads(astr),dtype)


# =============================================================================
# =============================================================================
# =============================================================================
# =============================================================================
def PSCF(specie):
    """
    The main PSCF function. Compute the PSCF according to the parameters in 'localParamPSCF.json'.
    The argument is the rank of the specie in the "species" in the 'localParamPSCF.json' file.
    If no argument is given, assume that there is only one specie and takes the first one.
    """

    # ===== Plot event                          ===============================
    def onclick(event):
        """ Find the BT which pass through this cell"""
    
        if event.button == 1 and (event.xdata != None and event.ydata != None):
            # x/y to lon/lat
            lon, lat = traj(event.xdata, event.ydata, inverse=True)
            lon = np.floor(lon*2)/2
            lat = np.floor(lat*2)/2
            print("Lon/Lat: %.2f / %.2f" %(lon, lat))
            # find all the BT
            for i in range(len(backTraj)):
                if backTraj[i].conc >= concCrit:
                    a=np.array([])
                    b=np.array([])
                    for j in range(len(backTraj[i].coord)):
                        lon_tmp = np.floor(backTraj[i].coord[j][0,:]*2)/2
                        lat_tmp = np.floor(backTraj[i].coord[j][1,:]*2)/2
                        a = lon_tmp==lon
                        b = lat_tmp==lat
                        if np.sum(a&b)!=0:
                            xx,yy = traj(backTraj[i].coord[j][0,:], backTraj[i].coord[j][1,:])
                            #print(lon_tmp,lat_tmp,xx,yy)
                            ax.plot(xx, yy, '-',color='0.75')#, marker='.')
                            print("date: %.10s | BT: %.13sh | [x]: %s"%(backTraj[i].global_date, backTraj[i].date[j], backTraj[i].conc))
            print("")
            event.canvas.draw()
    
        if event.button == 3:
            ax.lines=[]
            traj.plot(x_station, y_station, 'o', color='0.75')
            pmesh=traj.pcolormesh(x_map, y_map, PSCF, cmap='hot_r')
            event.canvas.draw()

    # ===== Load the json file                  ===================================
    with open(os.path.normpath('parameters/localParamPSCF.json'), 'r') as dataFile:
        param=json.load(dataFile)
    with open(os.path.normpath('parameters/locationStation.json'), 'r') as dataFile:
        locStation=json.load(dataFile)
    
    # ===== Initialisation                      ===================================
    # ===== Parameters
    lat0, lon0, alt0 = locStation[param["station"]]
    lon0             = float(lon0)
    lat0             = float(lat0)
    folder      = param["dirBackTraj"]
    prefix      = param["prefix"]
    add_hour    = json2arr(param["add_hour"], np.float64)
    resQuality  = param["resolutionQuality"][0]
    percentile  = json2arr(param["percentile"], np.float64)
    threshold   = json2arr(param["threshold"], np.float64)

    # ===== date
    dateAll = np.genfromtxt(param["Cfile"], delimiter=';', skip_header=1, usecols=[0], dtype=str)
    dateAll = str2date(dateAll)
    date    = list()
    sp      = specie2study(param["Cfile"], param["species"][specie])
    concAll = np.genfromtxt(param["Cfile"], delimiter=';', skip_header=1, usecols=[sp]) # Concentration
    conc    = list()
    # date format "dd/mm/yyyy hh:mm"
    dateMintmp  = np.array([param["dateMin"][2]+"/"+param["dateMin"][1]+"/"+param["dateMin"][0]+" 00:00"])
    dateMaxtmp  = np.array([param["dateMax"][2]+"/"+param["dateMax"][1]+"/"+param["dateMax"][0]+" 00:00"])
    dateMin     = str2date(dateMintmp)
    dateMax     = str2date(dateMaxtmp)
    for i,d in enumerate(dateAll):
        if (d > dateMin) & (d < dateMax):
            date.append(d)
            conc.append(concAll[i])

    # ===== concentration critic
    if param["percentileBool"]:
        if len(percentile)==1 and len(param["species"])!=1:
            percentile=np.tile(percentile, len(param["species"])) # repeat the same percentile for all species
        concCrit = sst.scoreatpercentile(conc, percentile[specie])
    else:
        if len(threshold)==1 and len(param["species"])!=1:
            threshold=np.tile(threshold, len(param["species"])) # repeat the same threshold for all species
        concCrit = threshold[specie]
    

    # ===== Main loop, take the back traj       ===================================
    backTraj = list()
    n   = np.array([[],[]])
    m   = np.array([[],[]])
    for d in range(len(date)):
        backTraj.append(makeBT(date[d], conc[d], list(), list(), list(), list()))
        # find all back traj for the date d
        for i in range(add_hour.shape[0]):
            backTraj[-1].date.append(date[d]+dt.timedelta(hours=add_hour[i]))
            # open back traj file
            datafile=folder+prefix+aammddhh(backTraj[-1].date[-1])
            if not os.path.isfile(datafile):
                print('Back-trajectory ' +prefix+aammddhh(backTraj[-1].date[-1])+ ' file is missing')
                continue
            else:
                # add the lon/lat of the BT
                nb_lin_to_skip = linecache.getline(datafile, 1).split()
                nb_lin_to_skip = int(nb_lin_to_skip[0])
                rainfall_idx = linecache.getline(datafile, nb_lin_to_skip+4).split()
                rainfall_col = rainfall_idx.index('RAINFALL')+11

                lat   = np.genfromtxt(datafile, skip_header = nb_lin_to_skip+5, usecols=[9])[:param["backTraj"]]
                lon   = np.genfromtxt(datafile, skip_header = nb_lin_to_skip+5, usecols=[10])[:param["backTraj"]]
                #T     = np.genfromtxt(datafile, skip_header = nb_lin_to_skip+5, usecols=[rainfall_col-1])[:param["backTraj"]]
                if param["rainBool"]:
                    rain  = np.genfromtxt(datafile, skip_header = nb_lin_to_skip+5, usecols=[rainfall_col])[:param["backTraj"]]
                #    backTraj[-1].rain.append(np.mean(rain).tolist())
                    if np.mean(rain)!=-0: # if it was raining at least one time
                        lat = lat[:np.where(rain!=0)[0][0]]
                        lon = lon[:np.where(rain!=0)[0][0]]

                #backTraj[-1].temp.append(np.min(T).tolist())
                #print(backTraj[-1].temp)
                backTraj[-1].coord.append(np.array([lon, lat]))

    # ===== convert lon/lat to 0, 0.5, 1, etc
    lon = np.arange(param["LonMin"], param["LonMax"]+0.01, 0.5) #+0.1 in order to have the max in the array
    lat = np.arange(param["LatMin"], param["LatMax"]+0.01, 0.5)
    lon_map, lat_map = np.meshgrid(lon, lat)
    ngrid = np.zeros((lat.size,lon.size))
    mgrid = np.zeros((lat.size,lon.size))
    for d in range(len(date)):
        for bt in range(len(backTraj[d].coord)):
            tmp = unique2d(np.floor(backTraj[d].coord[bt]*2)/2)
            #print(tmp)
            for i in range(tmp.shape[1]):
                idx_lon = np.where(lon==tmp[0,i])[0]
                idx_lat = np.where(lat==tmp[1,i])[0]
                ngrid[idx_lat, idx_lon] +=1
                if conc[d] >= concCrit:
                    mgrid[idx_lat, idx_lon] +=1

    n0 = np.where(ngrid!=0)

    PSCF = np.zeros(np.shape(ngrid))
    PSCF[n0] = mgrid[n0]/ngrid[n0]

    trajdensity = np.zeros(np.shape(ngrid))
    trajdensity[n0] = np.log10(ngrid[n0])

    # ===== Weighting function
    if param["wF"]:
        wF = np.zeros(np.shape(ngrid))
        if param["wFmanual"]:
            wFlim=np.array([ float(param["wFlim"][0]), float(param["wFlim"][1]), float(param["wFlim"][2]) ]) *trajdensity.max()
            wFval=np.array([ float(param["wFval"][0]), float(param["wFval"][1]), float(param["wFval"][2]), float(param["wFval"][3]) ])

            wF[ np.where( trajdensity <  wFlim[0]) ]=wFval[0]
            wF[ np.where((trajdensity >= wFlim[0]) & (trajdensity<wFlim[1]))]=wFval[1]
            wF[ np.where((trajdensity >= wFlim[1]) & (trajdensity<wFlim[2]))]=wFval[2]
            wF[ np.where( trajdensity >= wFlim[2]) ]=wFval[3]
        else:
            #m0 = np.where(mgrid !=0)
            #wF[m0] = np.log(mgrid[m0])/np.log(ngrid.max())
            wF[n0] = np.log(ngrid[n0])/np.log(ngrid.max())

        PSCF = PSCF * wF

    if param["smooth"]:
        PSCF=scipy.ndimage.filters.gaussian_filter(PSCF, 1)
        trajdensity=scipy.ndimage.filters.gaussian_filter(trajdensity, 1)


    # =========================================================================
    # ===== PLOT PART                       ===================================
    # =========================================================================

    # ===== Plot Back Traj (log(n+1))       ===================================
    if param["plotBT"]:
        figBT=plt.figure()
        m = Basemap(projection='merc', llcrnrlat=param["LatMin"], urcrnrlat=param["LatMax"], llcrnrlon=param["LonMin"], urcrnrlon=param["LonMax"], resolution=resQuality)#, lat_ts=49)
        x_BT, y_BT = m(lon_map, lat_map)
        m.drawcoastlines(color='black')
        m.drawcountries(color='black')
        x_station, y_station = m(lon0, lat0)
        cs = m.pcolormesh(x_BT, y_BT, trajdensity, cmap='hot_r')
        plt.title(param["station"]+'\nBack-traj probalility (log(n))')
        m.plot(x_station, y_station, 'o', color='0.75')

    
    # ===== Polar plot                      ===================================
    if param["polarPlot"]:
        r=np.zeros((lat.size, lon.size))
        phi=np.zeros((lat.size, lon.size))
        for i in range(len(lat)):
            for j in range(len(lon)):
                deltaLon = (lon[j]-math.floor(lon0*2)/2)
                deltaLat = (lat[i]-math.floor(lat0*2)/2)
                r[i,j] = math.sqrt( deltaLon**2 + deltaLat**2)
                phi[i,j] = math.atan2(deltaLat, deltaLon)
        phi[ np.where(phi < 0) ] = phi[ np.where(phi < 0) ] + 2*math.pi
    
        nPhi=[]
        mPhi=[]
        N=16
        theta = np.arange(0,361,22.5)
        theta = theta*math.pi/180
        nPhi.append( np.sum(ngrid[ np.where( phi <= math.pi/8)]))
        mPhi.append( np.sum(mgrid[ np.where( phi <= math.pi/8)]))
        for i in range(1, N):
            nPhi.append( np.sum( ngrid[ np.where( (theta[i-1]<phi) & (phi <= theta[i]) ) ] ) )
            mPhi.append( np.sum( mgrid[ np.where( (theta[i-1]<phi) & (phi <= theta[i]) ) ] ) )
        
        # ===== Plot part
        figPolar=plt.figure()
        xticklabel=['E', 'NE', 'N', 'NO', 'O', 'SO', 'S', 'SE']
    
        #axPolar = plt.subplot(121, projection='polar')
        #plt.title('N grid')
        #bars = axPolar.bar( theta[:-1], nPhi/np.sum(ngrid), width=math.pi/8)
        #axPolar.xaxis.set_ticklabels(xticklabel)
    
        axPolar = plt.subplot(111, projection='polar')
        bars = axPolar.bar( theta[:-1], mPhi/np.sum(mgrid), width=math.pi/8)
        axPolar.xaxis.set_ticklabels(xticklabel)
    
        plotTitle=param["station"] + ', ' + param["species"][specie] + " > "+str(concCrit) + '\nFrom ' + min(date).strftime('%Y/%m/%d') + ' to ' + max(date).strftime('%Y/%m/%d')
        plt.title(plotTitle)
        #figPolar.suptitle(plotTitle)

    # ===== Plot PSCF                       ===================================
    #print(PSCF.max())
    fig=plt.figure()
    ax = fig.add_subplot(111)
    #traj = Basemap(projection='merc', llcrnrlat=37.5, urcrnrlat=61, llcrnrlon=-20, urcrnrlon=25, resolution=resQuality)#, lat_ts=49)
    traj = Basemap(projection='merc', llcrnrlat=param["LatMin"], urcrnrlat=param["LatMax"], llcrnrlon=param["LonMin"], urcrnrlon=param["LonMax"], resolution=resQuality)#, lat_ts=49)
    traj.drawcoastlines()
    traj.drawcountries()
    traj.drawmapboundary()
    
    x_map, y_map = traj(lon_map, lat_map)
    pmesh=traj.pcolormesh(x_map, y_map, PSCF, cmap='hot_r')
    
    x_station, y_station = traj(lon0, lat0)
    traj.plot(x_station, y_station, 'o', color='0.75')
    plotTitle=param["station"] + ', ' + param["species"][specie] + " > "+str(concCrit) + '\nFrom ' + min(date).strftime('%Y/%m/%d') + ' to ' + max(date).strftime('%Y/%m/%d')
    plt.title(plotTitle)
    #plt.colorbar()
        
    cid = fig.canvas.mpl_connect('button_press_event', onclick)
    plt.show()


# This part is only if you want to run this file via command line.
# Be sure to have a correct 'localParamPSCF.json' file before running it... otherwhise you will have many error messages.
# The syntaxe is : python2 PSCF4GUI.py *args
# where *args is an integer and refer to the specie in 'species' in 'localParamPSCF.json'.
# If no arg is given, assume that the first specie in 'species' is wanted.
if __name__ == '__main__':
    if len(sys.argv)==1:
        p=Process(target=PSCF, args=(0,))
        p.start()
    else:
        for i in sys.argv[1:]:
            p= Process(target=PSCF, args=(int(i),))
            p.start()
