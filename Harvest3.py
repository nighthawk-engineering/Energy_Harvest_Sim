# -*- coding: utf-8 -*-
"""
Created on Mon May  7 14:58:05 2018

@author: mlgkschm
"""

import csv
from math import sqrt
from warnings import warn

# Q: How do you guarrantee the state names are not misspelled?
# A: Use this dict to check harvester state names for validity
st = {'off': 'off', 'cold': 'cold', 'warm': 'warm', 'full': 'full'}

##############################################################################
# A master clock object
class clock:
    def __init__(self,env,period):
        self.env = env
        self.period = period  # Primary clock period
        self.Tpost = period/10  # Secondary clock delay from primary
        self.tick = None  # Primary time marker, for computing
        self.tock = None  # Secondary time marker, for post processing
        self.req = {}  # list of devices relying on 'clock'
        self.running = True
        self.env.process(self.runTick(self.period))  # start Primary
        self.env.process(self.runTock(self.period))  # start Secondary
    
    def runTick(self,period):
        print('Clock start: @ %f' % self.env.now)
        #
        while len(self.req) == 0:
            self.tick = self.env.process(self.step(period))
            yield self.tick
        #
        while len(self.req) > 0:
            self.tick = self.env.process(self.step(period))
            yield self.tick
        #
        print('Clock stop: @ %f' % self.env.now)
        self.running = False
        self.tick = None
    
    def runTock(self,period):
        self.tock = self.env.timeout(self.Tpost)  # delay from T=0
        yield self.tock
        #
        while self.running:  # then start secondary clock
            self.tock = self.env.process(self.step(period))
            yield self.tock
        #
        print('Tock stop: @ %f' % self.env.now)
        self.tock = None
    
    def step(self,delT):
        yield self.env.timeout(delT)
    
    def start(self,req):
        print('Req clock start: %s @ %f' % (req.name,self.env.now))
        self.req[req] = req.name
    
    def stop(self,req):
        print('Req clock stop: %s @ %f' % (req.name,self.env.now))
        del self.req[req]

##############################################################################
# An object to collect data on any node
class scope:
    def __init__(self,env,clock,node,unit=1):
        self.env = env
        self.unit = unit
        self.name = 'Scope'+str(self.unit)
        self.clock = clock
        self.node_obj = node[0]
        self.node_atr = node[1]
        self.time = []
        self.data = []
        self.env.process(self.run())
    
    def run(self):
        #self.clock.start(self)
        collect = True
        while collect and self.clock.running:
            yield self.clock.tock
#            data = self.node()
            data = getattr(self.node_obj,self.node_atr)
            collect = defined(data)
            if collect:
                self.time.append(self.env.now)
                self.data.append(data)
        #self.clock.stop(self)

##############################################################################
# A class to switch something, 'obj', on and off, using method 'obj.en'
class OnOff:
    def __init__(self,env,clk,doList,obj):
        self.env = env
        self.clk = clk
        # doList is a list of sleep times in seconds, not cumulative
        self.doList = doList
        self.obj = obj
        self.env.process(self.run())
    
    def run(self):
        for sleep in self.doList:
            yield self.env.timeout(sleep)
            if not self.clk.running: break
            self.obj.en = not self.obj.en

##############################################################################
# Create an object to manage file-based power models
class Psrc:
    def __init__(self,env,I=None,V=None,R=None,unit=1,fname="src_data.csv",Tscale=1,Pscale=1,en=True):
        self.env = env
        self.unit = unit
        self._en = en
        self.Zsrc = 2.9 # TEG input impedance, ohms [historical]
        self._I = I
        self._V = V
        self._R = R
        self.Utot = 0
        self.nowP = 0
        self.name = 'Psrc'+str(self.unit)
        self.data = []
        self.datafile = fname
        with open(self.datafile, 'r') as f:
            csvData = csv.reader(f)
            for row in csvData:
                try:
                    self.data.append(
                            {'time': float(row[0])*Tscale, 
                             'data': float(row[1])*Pscale})
                except ValueError:
                    self.data.append(
                            {'time': row[0], 'data': row[1]})
        self.hdr = self.data.pop(0)  # remove and save the header
        self.env.process(self.run())
        
    def run(self):
        print('SRC start: @ %f' % self.env.now)
        self.nextSrc = self.data.pop(0)  # prime the dT machine
        #
        for row in self.data:
            self.prevSrc = self.nextSrc
            self.nextSrc = row
            sleep = self.nextSrc['time'] - self.prevSrc['time']
            yield self.env.timeout(sleep)
        self.prevSrc = self.nextSrc
        self.nextSrc = None
        print('SRC stop: @ %f' % self.env.now)

    @property
    def Psrc(self):
        # interpolate between two data points for Psrc @ env.now
        try:
            delP = self.nextSrc['data'] - self.prevSrc['data']
            delT = self.nextSrc['time'] - self.prevSrc['time']
            delNow = self.env.now - self.prevSrc['time']
            nowP = self.prevSrc['data'] + delP/delT * delNow
            self.nowP = nowP
            self.Utot += nowP if self.Utot <= 0.3571 else 0
            return(nowP)
        except TypeError:
            return(None)
    
    @property
    def P(self):
        return(self.Psrc if self.on else 0)
        
    @P.setter
    def P(self, P):
        warn('WARNING: Object ''Psrc'' cannot set P')
    
    @property
    def V(self):
        P = self.Psrc
        if not defined(P):
            return(P if self.on else 0)
        elif defined(self._V):
            V = self._V
        elif defined(self._I):
            V = P / self._I
        elif defined(self._R):
            V = sqrt(P * self._R)
        else:
            warn('WARNING: Object ''Psrc'' needs I or R defined to return V')
            V = None
        return(V if self.on else 0)
    
    @V.setter
    def V(self, V):
        if not defined(self._I) and not defined(self._R):
            self._V = V
        else:
            warn('WARNING: Object ''Psrc'' can set only one of V, I, R')
    
    @V.deleter
    def V(self):
        self._V = None
    
    @property
    def I(self):
        P = self.Psrc
        if not defined(P):
            return(P if self.on else 0)
        elif defined(self._I):
            I = self._I
        elif defined(self._V):
            I = P / self._V
        elif defined(self._R):
            I = sqrt(P / self._R)
        else:
            warn('WARNING: Object ''Psrc'' needs V or R defined to return I')
            I = None
        return(I if self.on else 0)
    
    @I.setter
    def I(self, I):
        if not defined(self._V) and not defined(self._R):
            self._I = I
        else:
            warn('WARNING: Object ''Psrc'' can set only one of V, I, R')
    
    @I.deleter
    def I(self):
        self._I = None
    
    @property
    def R(self):
        P = self.Psrc
        if not defined(P):
            return(P if self.on else 0)
        elif defined(self._R):
            R = self._R
        elif defined(self._I):
            R = P / self._I**2
        elif defined(self._V):
            R = self._V**2 / P
        else:
            warn('WARNING: Object ''Psrc'' needs I or V defined to return R')
            R = None
        return(R if self.on else 1e15)
    
    @R.setter
    def R(self, R):
        if not defined(self._V) and not defined(self._I):
            self._R = R
        else:
            warn('WARNING: Object ''Psrc'' can set only one of V, I, R')
    
    @R.deleter
    def R(self):
        self._R = None
    
    @property
    def on(self):
        return(self._en)
    
    @property
    def en(self):
        return(self._en)
    
    @en.setter
    def en(self,en):
        self._en = en

##############################################################################
# An object to create a fixed DC current, voltage or resistive load
# Note that the 'switch' object can turn this on and off using the 'en' method
class sink:
    def __init__(self,env,I=None,V=None,R=None,unit=1):
        self.env = env
        self.unit = unit
        self.name = "I"+str(self.unit)
        self._I = I
        self._V = V
        self._R = R
        self._en = True
    
    @property
    def R(self):
        if defined(self._R):
            R = self._R
        elif defined(self._I) and defined(self._V):
            R = self._V / self._I
        else:
            warn('WARNING: Object ''sink'' needs I and V defined to return R')
            R = None
        return(R if self.on else 1e15)
    
    @R.setter
    def R(self, R):
        if defined(self._R):
            self._R = R
        elif defined(self._V) and not defined(self._I):
            self._R = R
        elif not defined(self._V) and defined(self._I):
            self._R = R
        else:
            warn('WARNING: Object ''sink'' can set only two of V, I, R')
    
    @R.deleter
    def R(self):
        self._R = None
    
    @property
    def V(self):
        if defined(self._V):
            V = self._V
        elif defined(self._I) and defined(self._R):
            V = self._I * self._R
        else:
            warn('WARNING: Object ''sink'' needs I and R defined to return V')
            V = None
        return(V if self.on else 0)
    
    @V.setter
    def V(self, V):
        if defined(self._V):
            self._V = V
        elif defined(self._I) and not defined(self._R):
            self._V = V
        elif not defined(self._I) and defined(self._R):
            self._V = V
        else:
            warn('WARNING: Object ''sink'' can set only two of V, I, R')

    @V.deleter
    def V(self):
        self._V = None
    
    @property
    def I(self):
        if defined(self._I):
            I = self._I
        elif defined(self._V) and defined(self._R):
            I = self._V / self._R
        else:
            warn('WARNING: Object ''sink'' needs V and R defined to return I')
            I = None
        return(I if self.on else 0)
    
    @I.setter
    def I(self, I):
        if defined(self._V):
            self._I = I
        elif defined(self._V) and not defined(self._R):
            self._I = I
        elif not defined(self._V) and defined(self._R):
            self._I = I
        else:
            warn('WARNING: Object ''sink'' can set only two of V, I, R')
    
    @I.deleter
    def I(self):
        self._I = None
    
    @property
    def P(self):
        if defined(self._V) and defined(self._I):
            P = self._V * self._I
        elif defined(self._V) and defined(self._R):
            P = self._V**2 / self._R
        elif defined(self._I) and defined(self._R):
            P = self._I**2 * self._R
        else:
            warn('WARNING: Object ''sink'' needs two of V, I and R defined to return P')
            P = None
        return(P if self.on else 0)
    
    @P.setter
    def P(self, P):
        warn('WARNING: Object ''sink'' can''t set P')
    
    @P.deleter
    def P(self):
        self._P = None
    
    @property
    def on(self):
        return(self._en)
    
    @property
    def en(self):
        return(self._en)
    
    @en.setter
    def en(self,en):
        self._en = en

##############################################################################
# Create a capacitor model
class cap:
    def __init__(self,env,val,unit=1):
        self.env = env
        self.unit = unit
        self.name = "C"+str(self.unit)
        self._C = val
        self._Q = 0
    
    @property
    def C(self):
        return(self._C)
    
    @property
    def Q(self):
        # charge: Q = C*V
        return(self._Q)
    
    @Q.setter
    def Q(self,Q):
        self._Q = Q
    
    @property
    def V(self):
        # voltage: V = Q/C
        return(self._Q / self._C)
    
    @V.setter
    def V(self, V):
        self._Q = self._C * V
    
    @property
    def U(self):
        # energy: U = 1/2*C*V^2
        return(self._C*self.V**2/2)
    
    @U.setter
    def U(self, U):
        # U = 1/2*C*V^2
        # V = sqrt(2*U/C) = sqrt(2*U)/sqrt(C) = sqrt(2*U*C)/C
        # Q = C*V = sqrt(2*U*C)
        self._Q = sqrt(2*U*self._C)
    
    def addQ(self,dQ):
        self._Q += dQ
        return(self._Q)

##############################################################################
# Create a model of the harvester half of the bq25570, the input
# Collected data is stored in capacitors, 'stor' and 'bat'
class harvester():
    def __init__(self,env,clk,inp,stor,bat,unit=1,en=True):
        self.env = env
        self.clock = clk
        self.unit = unit
        self.name = "HVST"+str(self.unit)
        # input pins
        self.inp = inp  # the input power object
        # bidi pins
        self.stor = stor
        self.bat = bat
        # state variable
        # states: off, cold, warm, full
        self.state = st['off']
        self.stateLog = {'time': [0], 'data': [self.state]}
        # circuit parameters
        self._en = en  # enable bit
        self.Zin = self.inp.Zsrc  # Internal impedance, facing SRC [historical]
        self.next_Pin = {'time': 0, 'data': 0}
        self.loss_cold = 0.95  # This is loss, not efficiency
        self.loss_warm = 0.25
        # bq25570 threshold triggers
        self.coldstart = 0.1  # coldstart trigger
        self.chgen = 1.73  # main boost trigger
        self.bat_uv = 2.0  # battery undervoltage limit -- switch out batt
        self.bat_ok = 2.5
        self.bat_ov = 5.5  # battery overvoltage limit -- turn off boost
        # Is Cstor&Cbat got enough charge on 'em?
        self._batOK = False
        # debug parameters
        self._dQ = 0
        self._dU = 0
        # start collecting energy
        self.env.process(self.run())
        self.env.process(self.nextState())
    
    def run(self):  # runs on its own, off of 'tick'
        # precharge the battery
        self.bat.V = self.chgen
        #
        self.clock.start(self)
        gen = self.nextQ()
        while gen:
            yield self.clock.tick
            self._dQ = 0  # for debug
            self._dU = 0  # for debug
            gen = self.nextQ()
        self.clock.stop(self)
    
    def nextQ(self):
        self.prev_Pin = self.next_Pin
        self.next_Pin = {'time': self.env.now, 'data': self.inp.P}
        gen = defined(self.next_Pin['data'])
        if gen:
            self.next_Pin['data'] *= 1-self.loss
            # Vc*Ic = P = Vi*Ii; 
            # U = P*T
            # dU = U1-U0 = P*dT
            # U0 = 1/2*C*V0^2
            # U1 = U0 + P*dT = 1/2*C*V1^2
            # V1^2 = (U0 + P*dT)*2/C
            # V1 = sqrt((U0 + P*dT)*2)/sqrt(C)
            # V1 = sqrt((U0 + P*dT)*2*C)/C
            # Q1 = C*V1 = sqrt((U0 + P*dT)*2*C)
            # dQ = Q1 - Q0
            dT = self.next_Pin['time'] - self.prev_Pin['time']
            dU = self.next_Pin['data']*dT
            U0 = self.stor.U
            Q1 = sqrt((U0 + dU)*2*self.stor.C)
            Q0 = self.stor.Q
            dQ = Q1 - Q0
            if self.state == st['cold']:
                self.boost(dQ)
            elif self.state == st['warm']:
                self.boost(dQ)
            elif self.state == st['full']:
                self.balance(self.stor, self.bat)  # share charge w/bat
            else:
                None
            self._dU = dU
        return(gen)
    
    def boost(self,dQ):
        self.stor.addQ(dQ)
        if self.state == st['warm']:
            self.balance(self.stor, self.bat)  # share charge w/bat
        elif self.state == st['full']:
            self.balance(self.stor, self.bat)  # share charge w/bat
        else:
            None
        self._dQ = dQ  # for debug
    
    def balance(self,C1,C2):  # balance charge so that Vstor == Vbat
        dQ = (C1.Q * C2.C - C2.Q * C1.C) / (C1.C + C2.C)
        C1.addQ(-dQ)
        C2.addQ(dQ)
        if self.stor.V >= self.bat_ov:
            self.stor.V = self.bat_ov
            self.bat.V = self.bat_ov
    
    def sinkU(self,dU):
        # dU = P*dT = U1-U0
        # U0 = 1/2*C*V0^2
        # U1 = U0 + dU = 1/2*C*V1^2
        # V1^2 = (U0 + dU)*2/C
        # V1 = sqrt((U0 + dU)*2)/sqrt(C)
        # V1 = sqrt((U0 + dU)*2*C)/C
        # Q1 = C*V1 = sqrt((U0 + dU)*2*C)
        # dQ = Q1 - Q0
        U0 = self.stor.U + self.bat.U
        Q1 = sqrt((U0 + dU)*2*(self.stor.C+self.bat.C))
        Q0 = self.stor.Q + self.bat.Q
        dQ = Q1 - Q0
        self.boost(dQ)

    def nextState(self):  # runs on its own, off of 'tock'
        while self.clock.running:
            # measure the battery voltage
            self._batOK = (self.stor.V >= self.bat_ok)
            #
            # update the state machine
            _prevState = self.state
            if not self.en:
                self.state = st['off']
            elif self.stor.V < self.chgen:
                self.state = st['cold']
            elif self.stor.V < self.bat_ov*0.999:
                self.state = st['warm']
            elif self.stor.V >= self.bat_ov*0.999:
                self.state = st['full']
            else:
                print('ERROR: state: no state found')
            if _prevState != self.state:  # log the state change
                self.logState(_prevState)
                self.logState()
            yield self.clock.tock
        #print('WARNING: nextState exiting!')
    
    def logState(self,state=None):
        if not defined(state):
            state = self.state
        self.stateLog['time'].append(self.env.now)
        self.stateLog['data'].append(state)

    @property
    def loss(self):
        if self.state == st['cold']:
            _loss = self.loss_cold
        elif self.state == st['warm']:
            _loss = self.loss_warm
        elif self.state == st['full']:
            _loss = self.loss_warm
        else:
            _loss = 1  # Off state
        return(_loss)
    
    @property
    def batOK(self):
        return(self._batOK)
    
    @property
    def on(self):
        return(self._en)
    
    @property
    def en(self):  # enable bit
        return(self._en)
    
    @en.setter
    def en(self, en):
        self._en = en
        
    @property
    def dQ(self):  # for debug
        return(self._dQ)
    
    @dQ.setter
    def dQ(self,dQ):  # for debug
        self._dQ = dQ
    
    @property
    def dU(self):  # for debug
        return(self._dU)
    
    @dU.setter
    def dU(self,dU):  # for debug
        self._dU = dU
    
    @property
    def Ustored(self):  # for debug
        return(self.stor.U+self.bat.U)

##############################################################################
# Create a model of the buck converter half of the bq25570, the output
# Energy is drawn from 'stor' capacitor, via 'sinkU' method in 'harvester'
class converter:
    def __init__(self,env,clock,Estor,Vout,Iout,unit=1,en=True):
        self.env = env
        self.clock = clock
        self.unit = unit
        self.name = "CNVTR"+str(self.unit)
        # input pins
        self._en = en  # enable bit
        # bidi pins
        self.Estor = Estor
        # buck converter output parameters
        self._V = Vout  # buck converter's output voltage
        self._I = Iout  # record of current load at the output
        # circuit parameters
        self.prev_Pout = {}
        self.next_Pout = {'time': 0, 'data': 0}
        self._loss = 0.10
        # bq25570 threshold triggers
        self.bat_ok = Estor.bat_ok
        # debug parameters
        self._dU = 0
        # start collecting energy
        self.env.process(self.run())
    
    def run(self):
        # tell the power source the output voltage
        self._I.V = self._V
        #
        self.clock.start(self)
        gen = self.nextU()
        while gen:
            if self.clock.running:
                yield self.clock.tick
                gen = self.nextU()
            else:
                gen = False
        self.clock.stop(self)
    
    def nextU(self):
        self.prev_Pout = self.next_Pout
        self.next_Pout = {'time': self.env.now, 'data': self.P}
        gen = defined(self.next_Pout['data'])
        if gen:
            dT = self.next_Pout['time'] - self.prev_Pout['time']
            self.next_Pout['data'] /= 1-self.loss
            dU = self.next_Pout['data'] * dT
            self.buck(-dU)
        return(gen)
    
    def buck(self,dU):
        if self.on:
            self.Estor.sinkU(dU)
        self._dU = dU  # for debug
    
    @property
    def loss(self):
        return(self._loss)
    
    @property
    def V(self):
        return(self._V if self.on else 0)
    
    @property
    def I(self):
        return(self._I.I if self.on else 0)
    
    @property
    def P(self):
        return(self._I.P if self.on else 0)
    
    @property
    def dU(self):  # for debug
        return(self._dU)
    
    @dU.setter
    def dU(self,dU):  # for debug
        self._dU = dU
    
    @property
    def on(self):
        return(self.en and self.Estor.batOK)

    @property
    def en(self):  # enable bit
        return(self._en)
    
    @en.setter
    def en(self, en):
        self._en = en

##############################################################################
##############################################################################
##############################################################################
# useful functions

# A useful function to sum two lists (better way?)
def list_m(a, b):
    c = []
    for i in range(len(a)):
        c.append(a[i]+b[i])
    return(c)

def defined(var):
    return(var != None)