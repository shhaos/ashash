import os
from subprocess import Popen, PIPE
from collections import defaultdict
import datetime
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pylab as plt
import glob
import json
import cPickle as pickle
import ashash
import numpy as np
import random
import scipy.stats as sps
import errno
import scipy
from collections import OrderedDict
import statsmodels.stats.api as sms
from  more_itertools import unique_justseen

def ecdf(a, **kwargs):
    sorted=np.sort( a )
    yvals=np.arange(len(sorted))/float(len(sorted))
    plt.plot( sorted, yvals, **kwargs )


def eccdf(a, **kwargs):
    sorted=np.sort( a )
    yvals=np.arange(len(sorted))/float(len(sorted))
    plt.plot( sorted, 1-yvals, **kwargs )


def smooth(x, N):
    return np.convolve(x, np.ones((N,))/N, mode='valid') 


def tableResults(path, newFormat=True):
    for filename in glob.glob(path):
        for line in open(filename,"r"):

            time = line.partition("|")[0]
            anomalies = line.rpartition("|")[2]
            anomalies = anomalies.replace("(", "[").replace(")", "]").replace("'", '"')
            anomalies = json.loads(anomalies)

            if len(anomalies):
                for ano in anomalies:
                    if ano[1]>11:
                        print time, ano, filename
            


def extractData(start, end, monitoredAS=None, filterBGPmsg=None):

    #set filenames
    output = "../results/studyCases/AS{ma}_{ye}{mo:02d}{da:02d}T{ho:02d}{mi:02d}/".format(ma=monitoredAS, ye=start.year, mo=start.month, da=start.day, ho=start.hour, mi=start.minute)
    dataDirectory = "/data/routeviews/archive.routeviews.org/route-views.linx/bgpdata/{ye}.{mo:02d}/".format(ye=start.year, mo=start.month)
    ribfile = dataDirectory+"RIBS/rib.{ye}{mo:02d}{da:02d}.{ho:02d}00.bz2".format(ye=start.year, mo=start.month, da=start.day, ho=start.hour)
    updatefiles = []
    d = start
    while d < end:
        updatefiles.append(dataDirectory+"UPDATES/updates.{ye}{mo:02d}{da:02d}.{ho:02d}{mi:02d}.bz2".format(ye=d.year, mo=d.month, da=d.day, ho=d.hour, mi=d.minute))
        d += datetime.timedelta(minutes=15)


    #make the graph before and after the event
    if monitoredAS is None:
        params = ["python2", "ashash.py", "--plot", ribfile]
    else:
        params = ["python2", "ashash.py", "-f "+str(monitoredAS), "--plot", ribfile]

    if len(updatefiles)==0:
        updatefiles.append("None")

    params.extend(updatefiles)
    params.append(output)
    p1 = Popen(params)


    #retrieve BGP messages if filter is given
    if not filterBGPmsg is None:
        outFile = open(output+"bgpmessages_%s.txt" % filterBGPmsg, "w")
        for fi in updatefiles:
            print fi
            p2 = Popen(["bgpdump", "-m", "-v", fi], stdout=PIPE) 
            p3 = Popen(["grep",str(filterBGPmsg)], stdin=p2.stdout, stdout=outFile)
            p3.wait()

    p1.wait()

def longStats(af = 4, filter=None):
    dataDirectory = "/data/routeviews/archive.routeviews.org/route-views.linx/bgpdata/"
    
    space = 1
    yearRange = range(2004, 2017)
    #monthRange = range(1,13)
    monthRange = [6] #range(1,13)
    day = 15
    dateRange = []

    tier1 = {"3356":[], "1299":[], "174":[] ,"2914":[],"3257":[]}#, "6453":[], "3491":[], "701":[], "1239":[], "6762":[]}

    # Find the first RIB files for each year
    ribFiles = []
    for ye in yearRange:
        for month in monthRange:
            ribs = glob.glob(dataDirectory+"{ye}.{mo:02d}/RIBS/rib.{ye}{mo:02d}{da:02d}.*.bz2".format(ye=ye, mo=month, da=day))
            ribs.sort()
            if len(ribs) < 1:
                continue
            ribFiles.append(((ye,month,day),ribs[0]))
            dateRange.append(datetime.datetime(ye,month,day))

    outDir = "../results/longStats_space%s_ipv%s/" % (space, af)
    try:
        os.makedirs(os.path.dirname(outDir))
    except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise

    plt.figure()
    ccmap = mpl.cm.get_cmap('copper_r')
    # Using contourf to provide my colorbar info, then clearing the figure
    Z = [[0,0],[0,0]]
    CS3 = plt.contourf(Z, yearRange, cmap=ccmap)
    plt.clf()
    for i, (date, ribFile) in enumerate(ribFiles):
        print date
        if filter is None:
            centralityFile = outDir+"/%s%02d%02d_af%s.pickle" % (date[0], date[1], date[2], af)
            fList = None
        else:
            centralityFile = outDir+"/%s%02d%02d_AS%s_af%s.pickle" % (date[0], date[1], date[2],filter, af)
            fList = [filter]

        if not os.path.exists(centralityFile):
            rtree, _ = ashash.readrib(ribFile, space, af, filterAS=fList) 
            asAggProb, asProb, _ = ashash.computeCentrality(rtree.search_exact("0.0.0.0/0").data, space, filterAS=filter)
            pickle.dump((asAggProb, asProb), open(centralityFile, "wb"))
        else:
            asAggProb, asProb = pickle.load(open(centralityFile,"rb"))

        if asAggProb is None or len(asAggProb) < 1:
            continue

        if filter is None and af==4:
            for k,v in tier1.iteritems():
                v.append(asAggProb[str(k)])

        if not filter is None:
            del asAggProb[str(filter)]


        sortedAS = sorted(asAggProb, key=lambda k: asAggProb[k], reverse=True) 
        i=0
        while i<len(sortedAS) and asAggProb[sortedAS[i]]>.05:
            print "%s: %s" % (sortedAS[i], asAggProb[sortedAS[i]])
            i+=1

        eccdf(asAggProb.values(), lw=1.3, label=date[0],c=ccmap(i/float(len(ribFiles)) ) )
        # print date
        # maxKey = max(asAggProb, key=asAggProb.get)
        # print "AS%s = %s" % (maxKey, asAggProb[maxKey]) 

    plt.grid(True)
    #plt.legend(loc="right")
    plt.colorbar(CS3)
    plt.xscale("log")
    plt.yscale("log")
    #plt.yscale("log")
    # plt.xlim([10**-8, 10**-2])
    if filter is None:
        plt.xlim([10**-7, 1.1])
    else:
        plt.xlim([10**-7, 1.1])
    # plt.ylim([10**-3, 1.1])
    plt.xlabel("AS hegemony")
    plt.ylabel("CCDF")
    plt.tight_layout()
    if filter is None:
        plt.title("IPv%s" % af)
        plt.savefig(centralityFile.rpartition("/")[0]+"/hegemonyLongitudinal_af%s.eps" % af)
    else:
        plt.title("AS%s (IPv%s)" % (filter, af))
        plt.savefig(centralityFile.rpartition("/")[0]+"/hegemonyLongitudinal_AS%s_af%s.eps" % (filter, af))

    if filter is None and af==4:
        fig = plt.figure(figsize=(10,3))
        for k,v in tier1.iteritems():
            plt.plot(dateRange, v, label="AS"+k)
        plt.ylim([0,0.3])
        plt.grid(True)
        plt.ylabel("AS hegemony")
        plt.xlabel("Time")
        plt.legend(loc="center", bbox_to_anchor=(0.5, 1), ncol=len(tier1))
        plt.tight_layout()
        plt.savefig(centralityFile.rpartition("/")[0]+"/tier1.eps")


def compareToCaidaRank():
    space = 1
    af = 4
    dataDirectory = "/data/routeviews/archive.routeviews.org/route-views.linx/bgpdata/"

    # Load Caida as rank
    # caida = np.genfromtxt("../data/20160601_asRank.csv", dtype=str, delimiter=",")
    caida = np.genfromtxt("../data/20160601_asRank.csv", dtype=str, delimiter=",")

    centralityFile = "../results/caidaRank/20160601.0000.pickle"
    ribFile = dataDirectory+"2016.06/RIBS/rib.20160601.0000.bz2"
    if not os.path.exists(centralityFile):
        rtree, _ = ashash.readrib(ribFile, space, af) 
        asAggProb, asProb, _ = ashash.computeCentrality(rtree.search_exact("0.0.0.0/0").data, af)
        pickle.dump((asAggProb, asProb), open(centralityFile, "wb"))
    else:
        asAggProb, asProb = pickle.load(open(centralityFile,"rb"))

    # sortedAs = sorted(asAggProb, key=lambda k: asAggProb[k], reverse=True) 
    ourRanks = dict(zip(asAggProb.keys(),scipy.stats.rankdata( 1.0-np.array(asAggProb.values()))))

    # r = np.arange(1,10)
    # topList = list(r*10)
    # topList.extend(r*100)
    # topList.extend(r*1000)
    # topList.extend(range(10000, 50000, 10000))
    # topList = [-1]
    topList = sorted(np.unique(caida[:,0]).astype(int))
    print len(topList)
    x=[]
    y=[]
    for top in topList:
        print top
        x.append(top)
        us = [] 
        caidaFiltered = []
        for rank, asn in caida[:top]:
            if asn in ourRanks:
                us.append(ourRanks[asn])
                caidaFiltered.append(rank)

        res = scipy.stats.spearmanr(caidaFiltered, us)
        # res = scipy.stats.kendalltau(caidaFiltered, us)
        # res = scipy.stats.kruskal(caidaFiltered, us)
        print res
        y.append(res[0])

    plt.figure()
    plt.plot(caidaFiltered,us,"+")
    plt.savefig("../results/caidaRank/rankComparison.eps")
        
    plt.figure()
    plt.plot(x,y,"x-")
    # plt.plot(smooth(x,50),smooth(y,50),"x-")
    plt.xscale("log")
    plt.xlabel("CAIDA top ASN")
    plt.ylabel("Correlation coeff.")
    plt.tight_layout()
    plt.savefig("../results/caidaRank/SpearmanCorrelation.eps")

    return caidaFiltered, us


def peerSensitivity():
    space = 1
    af = 4
    allasCount = {}
    resultsFile = "../results/peerSensitivity/KLdiv_%s.pickle"
    collectorsDataFile = "../results/peerSensitivity/collectorData.pickle"
    allPeersFile = "../results/peerSensitivity/allPeersDist.pickle"
    collectorsDist = []
    results = defaultdict(list)

    if not os.path.exists(resultsFile % "Betweenness"):
        ribFiles = glob.glob("/data/routeviews/archive.routeviews.org/*/*/RIBS/rib.20160601.0000.bz2")
        ribFiles.extend(glob.glob("/data/routeviews/archive.routeviews.org/*/*/*/RIBS/rib.20160601.0000.bz2"))
        ribFiles.extend(glob.glob("/data/ris/*/*/bview.20160601.0000.gz"))
        ribFiles.append("/data/bgpmon/ribs/201606/ribs") 
        
        for i, ribFile in enumerate(ribFiles):
            words = ribFile.split("/")
            if "routeviews" in ribFile:
                if words[-4] == "route-views3":
                    label = "rv3"
                elif words[-5] == "archive.routeviews.org" and words[-4] == "bgpdata":
                    label = "rv2"
                elif not "." in words[-5] and words[-5].startswith("route-views"):
                    label = "rv"+words[-5][-1]
                else:
                    label = words[-5].split(".")[-1]
            elif "ris" in ribFile:
                label = words[-3]
            else:
                label = "bgpmon"

            asCountFile = "../results/peerSensitivity/20160601.0000_asCount%s.pickle" % (i)
            if not os.path.exists(asCountFile):
                rtree, _ = ashash.readrib(ribFile, space, af) 
                asCount = rtree.search_exact("0.0.0.0/0").data
                asHegemony, _, nbPeers = ashash.computeCentrality(asCount, space)
                # asBetweenness = ashash.computeBetweenness(asCount, space)
                pickle.dump((asCount, asHegemony, nbPeers), open(asCountFile, "wb"))
            else:
                asCount, asHegemony, nbPeers = pickle.load(open(asCountFile,"rb"))


            collectorsDist.append( (label, nbPeers, asHegemony) )

            print "%s: %s peers" % (label, len(asCount)) 
            for peer, count in asCount.iteritems():
                if count["totalCount"]>2000000000:
                    if not peer in allasCount:
                        allasCount[peer] = count
                    else:
                        print "Warning: peer %s is observed multiple times (%s)" % (peer, ribFile)

        asHegemonyRef, _, nbPeers = ashash.computeCentrality(allasCount, space)
        asBetweennessRef, _, _ = ashash.computeBetweenness(allasCount, space)
        pickle.dump((asHegemonyRef, asBetweennessRef, nbPeers), open(allPeersFile,"wb"))
        

        for metricLabel, ref, computeMetric in [("Hegemony", asHegemonyRef, ashash.computeCentrality),
                ("Betweenness", asBetweennessRef, ashash.computeBetweenness)]:

            if not os.path.exists(resultsFile % metricLabel):
                # Remove AS with a score of 0.0
                toremove = [asn for asn, score in ref.iteritems() if score==0.0]
                for asn in toremove:
                    del ref[asn]

                minVal = min(ref.values())

                nbPeersList = range(0, len(allasCount), 10)
                nbPeersList[0] = 1

                for nbPeers in nbPeersList:
                    tmp = []
                    for _ in range(10):

                        # Randomly select peers
                        peersIndex = random.sample(range(len(allasCount)), nbPeers)

                        asCount = {}
                        for p in peersIndex:
                            asCount[allasCount.keys()[p]] = allasCount.values()[p]

                        asMetric, _, _ = computeMetric(asCount, space)

                        # Remove AS with a score == 0.0
                        toremove = [asn for asn, score in asMetric.iteritems() if score==0.0]
                        if not toremove is None:
                            for asn in toremove:
                                del asMetric[asn]

                        # Set the same number of ASN for both distributions
                        missingAS = set(ref.keys()).difference(asMetric.keys())
                        if not missingAS is None:
                            for asn in missingAS:
                                asMetric[asn] = minVal

                        # Compute the KL-divergence
                        dist = [asMetric[asn] for asn in ref.keys()]
                        kldiv = sps.entropy(dist, ref.values())
                        tmp.append(kldiv)


                    results[metricLabel].append(tmp)
                    print tmp

                # save final results
                pickle.dump((nbPeersList, results[metricLabel]),open(resultsFile % metricLabel,"wb"))
                pickle.dump(collectorsDist, open(collectorsDataFile,"wb"))
            else:
                (nbPeersList, results[metricLabel]) = pickle.load(open(resultsFile % metricLabel,"rb"))
                collectorsDist = pickle.load(open(collectorsDataFile,"rb"))

    else:
        for metricLabel in ["Hegemony", "Betweenness"]:
            nbPeersList, results[metricLabel] = pickle.load(open(resultsFile % metricLabel,"rb"))
        collectorsDist = pickle.load(open(collectorsDataFile,"rb"))
        asHegemonyRef, asBetweennessRef, allFullFeedPeers = pickle.load(open(allPeersFile,"rb"))
        #return asHegemonyRef

    def plotRef(references, legendFmt="%s", alpha=1.0):
        for asDistRef, metricLabel, color in references:
            m = np.mean(results[metricLabel][1:], axis=1)
            s = np.std(results[metricLabel][1:], axis=1)
            # mi = m-np.min(results[metricLabel][1:], axis=1)
            # ma = np.max(results[metricLabel][1:], axis=1)-m
            # mi, ma = sms.DescrStatsW(results[metricLabel][1:]).tconfint_mean(alpha=0.1)
            mi = np.min(results[metricLabel][1:], axis=1)
            ma = np.max(results[metricLabel][1:], axis=1)
            x = nbPeersList[1:]

            plt.fill_between(x, mi, ma, facecolor=color, alpha=alpha*0.5)
            # plt.plot(x, m,"-+", ms=4, color="0.6", label="Randomly selected") 
            # plt.plot(x, m,"-+", ms=4, color="0.6", label="Random peers (%s)" % metricLabel) 
            try:
                plt.plot(x, m,"-o", ms=3, label=legendFmt % metricLabel, color=color, alpha=alpha) 
            except TypeError:
                plt.plot(x, m,"-o", ms=3, label=legendFmt, color=color, alpha=alpha) 
            # plt.errorbar(x,m, [mi, ma], fmt="C3.", ms=4)
            plt.xlabel("Number of peers")
            plt.ylabel("KL divergence")
            # plt.yscale("log")
            plt.legend()
            plt.tight_layout()
    
    # Compare betweenness and hegemony
    plt.figure()
    plotRef([(asHegemonyRef, "Hegemony", "C0"), (asBetweennessRef, "Betweenness", "C5")])
    plt.ylim([0.00001, 1])
    plt.xscale("log")
    plt.savefig("../results/peerSensitivity/meanKL_%s.pdf" % metricLabel)

    # Compare collectors and random sample (hegemony):
    # Remove AS with a score of 0.0
    toremove = [asn for asn, score in asHegemonyRef.iteritems() if score==0.0]
    for asn in toremove:
        del asHegemonyRef[asn]
    minVal = min(asHegemonyRef.values())
    plt.figure()
    plotRef([(asHegemonyRef, "Hegemony", "C0")], legendFmt="Random peers", alpha=0.5)
    plt.xlabel("Number of peers")
    plt.ylabel("KL divergence")
    for collectorLabel, nbPeers, asHegemony in collectorsDist:
        if asHegemony is None :
            print "warning: ignore collector %s" % collectorLabel
            continue

        # Remove AS with a score == 0.0
        toremove = [asn for asn, score in asHegemony.iteritems() if score==0.0]
        if not toremove is None:
            for asn in toremove:
                del asHegemony[asn]

        # Set the same number of ASN for both distributions
        missingAS = set(asHegemonyRef.keys()).difference(asHegemony.keys())
        if not missingAS is None:
            for asn in missingAS:
                asHegemony[asn] = minVal

        # Compute the KL-divergence
        dist = [asHegemony[asn] for asn in asHegemonyRef.keys()]
        kldiv = sps.entropy(dist, asHegemonyRef.values())
        print "%s:\t %s peers \t  %s " % (collectorLabel, nbPeers, kldiv)
        if kldiv>0.4 :
            continue
        if collectorLabel.startswith("rrc"):
            plt.plot(nbPeers, kldiv,"C1x", label="RIS")
            collectorLabel = collectorLabel.replace("rrc","")
        elif collectorLabel == "bgpmon":
            plt.plot(nbPeers, kldiv,"C3^")
        else:
            plt.plot(nbPeers, kldiv,"C3+", label="Route Views")
        if kldiv<1 or nbPeers>10:
            plt.text(nbPeers+0.005, kldiv+0.005, collectorLabel, fontsize=8)

    # plt.yscale("log")
    # plt.xscale("log")
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = OrderedDict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())
    plt.ylim([0.00001, 0.4])
    plt.xlim([9, 50])
    plt.tight_layout()
    plt.savefig("../results/peerSensitivity/collectorDiversity.pdf")


    return (nbPeersList, results)


#Top 5 countries (bgp.he.net): 
# ["US", "CN", "BR", "IN", "RU"]
# 

def countryAnalysis(ccList=["US","CN","JP", "NL", "PK", "CU", "KP","DE"]):
    space = 1
    af = 4
    dataDirectory = "/data/routeviews/archive.routeviews.org/route-views.linx/bgpdata/"

    plt.figure()
    for cc in ccList:
        print cc
        centralityFile = "../results/country/20160601.0000_%s.pickle" % cc
        ribFile = dataDirectory+"2016.06/RIBS/rib.20160601.0000.bz2"
        if not os.path.exists(centralityFile):
            prefixes = ashash.getPrefixPerCountry(cc)
            rtree, _ = ashash.readrib(ribFile, space, af, filterPrefix=prefixes) 
            asAggProb, asProb, _ = ashash.computeCentrality(rtree.search_exact("0.0.0.0/0").data, af, filterPrefix=prefixes)
            pickle.dump((asAggProb, asProb), open(centralityFile, "wb"))
        else:
            asAggProb, asProb = pickle.load(open(centralityFile,"rb"))

        eccdf(asAggProb.values(), lw=1.3, label=cc , marker="o", ms=3)

        sortedAS = sorted(asAggProb, key=lambda k: asAggProb[k], reverse=True) 
        i=0
        while asAggProb[sortedAS[i]]>.05:
            print "%s: %s" % (sortedAS[i], asAggProb[sortedAS[i]])
            i+=1

    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("AS hegemony")
    plt.ylabel("CCDF")
    plt.xlim([10**-7, 1.1])
    plt.legend(loc="best")
    # plt.legend(loc="center", bbox_to_anchor=(0.5, 1.1), ncol=len(ccList), fontsize=6)
    plt.tight_layout()
    plt.savefig("../results/country/country_hegemonyDist.pdf")



def pathDerivativeDist():
    space = 1
    af = 4

    outDir = "../results/longStats_space%s_ipv%s/" % (space, af)
    dataDirectory = "/data/routeviews/archive.routeviews.org/route-views.linx/bgpdata/"
    filename = dataDirectory+"2016.06/UPDATES/updates.20160601.0000.bz2"

    centralityFile = outDir+"/%s%02d%02d_af%s.pickle" % (2016, 6, 15, af)
    asAggProb, asProb = pickle.load(open(centralityFile,"rb"))

    allDiff = []
    linDiff = []
    if filename.startswith("@bgpstream:"):
        p1 = Popen(["bgpreader", "-m", "-w", filename.rpartition(":")[2], "-p", "routeviews", "-c", "route-views.linx", "-t", "updates"], stdout=PIPE)
    else:
        p1 = Popen(["bgpdump", "-m", "-v", filename],  stdout=PIPE, bufsize=-1)
    
    for line in p1.stdout:
        res = line[:-1].split('|',15)

        if res[5] == "0.0.0.0/0":
            continue
        
        if af != 0:
            if af == 4 and ":" in res[5]:
                continue
            elif af == 6 and "." in res[5]:
                continue

        if res[2] == "W":
            continue
        else:
            zTd, zDt, zS, zOrig, zAS, zPfx, sPath, zPro, zOr, z0, z1, z2, z3, z4, z5 = res

            path = list(unique_justseen(sPath.split(" ")))

            try :
                # hegeAll = map(lambda x: round(asAggProb[x],3), path[1:-1])
                hegeAll = map(lambda x: asAggProb[x], path)
                hegeDiff = np.diff(hegeAll)
                allDiff.extend(list(hegeDiff))
                
                N = 11
                dim = np.linspace(0,1,N)
                interpData = np.interp(dim, np.linspace(0,1,len(hegeAll)), hegeAll)
                linDiff.append(interpData)
            except Exception:
                # print path
                # print "New AS"
                continue

    plt.figure()
    ecdf(allDiff)
    plt.xlim([-0.1, 0.1])
    plt.xlabel("Hegemony derivative")
    plt.ylabel("CDF")
    plt.tight_layout()
    plt.savefig("../results/pathDerivative/derivativeDist.pdf")

    lda = np.array(linDiff)
    plt.figure()
    # plt.plot(dim, lda.mean(axis=0),"o-")
    plt.errorbar(dim, lda.mean(axis=0), lda.std(axis=0)/np.sqrt(N), fmt="o-")
    plt.xlabel("Relative position in the path")
    plt.ylabel("AS hegemony")
    plt.xlim([-0.03, 1.03])
    plt.tight_layout()
    plt.savefig("../results/pathDerivative/meanHegemony.pdf")


    return lda


def testPath():
    space = 1
    af = 4
    outDir = "../results/longStats_space%s_ipv%s/" % (space, af)
    dataDirectory = "/data/routeviews/archive.routeviews.org/route-views.linx/bgpdata/"
    # dataDirectory = "/data/routeviews/archive.routeviews.org/bgpdata/"

    allRes = {}
    centralityFile = outDir+"/%s%02d%02d_af%s.pickle" % (2015, 6, 15, af)
    asAggProb, asProb = pickle.load(open(centralityFile,"rb"))

    for day in range(1,31):
        for hour in range(24):
            for time in [0,15,30,45]:
                date = "201506%02d.%02d%02d" % (day, hour, time)
                print date
                updateFile = dataDirectory+"2015.06/UPDATES/updates.%s.bz2" % date

                res = ashash.detectValley(asAggProb, updateFile) 
                allRes[date] = res

    return allRes
