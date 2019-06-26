# -*- coding: utf-8 -*-
"""
Created on Mon May  7 14:47:28 2018

@author: mlgkschm
"""

import simpy
import Harvest3 as hvst
from Harvest3 import list_m
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

clock_period = 0.001
stop_time = 50
Stor = 4.7e-6  # Farads
#Bat = 23.2e-3  # Farads
#Bat = 53.5e-3  # Farads
Bat = 52.5e-3  # Farads
Vout = 2.5
Iout = 50e-3  # used by 'load', not by 'dsply'

###################################################

# create the SimPy environment
env = simpy.Environment()
# create the timing clock
clk = hvst.clock(env,clock_period)
# Import the TEG model, from measured data
teg = hvst.Psrc(env,unit=1,fname="teg_data.csv")
# Create the Cstor and Cbat capacitor models
Cstor = hvst.cap(env,Stor,unit="stor")
Cbat = hvst.cap(env,Bat,unit="bat")
# Create the energy harvester half of the bq25570 chip, the input
harvester = hvst.harvester(env,clk,teg,Cstor,Cbat,unit=1)

# Option 1: Create a current load model
load = hvst.sink(env,I=Iout)
# Option 2: Create the software driven display model, from measured data
dsply = hvst.Psrc(env,unit=1,fname="display_data.csv")

# Use Iload to switch between the two load models:
Iload = dsply  # Switched current load model
#Iload = dsply  # Display model

# Create the buck converter half of the bq25570 chip, the output
buckOut = hvst.converter(env,clk,harvester,Vout,Iload,unit=1,en=True)

# Create 'switch', an object to turn the load on and off
if Iload == load:
    doList = [1,4,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3]
    switch = hvst.OnOff(env,clk,doList,buckOut)

###################################################
# Probe the simulation in preparation of plotting data

prb_teg   = hvst.scope(env,clk,(teg,'P'))
prb_Utot  = hvst.scope(env,clk,(teg,'Utot'))
prb_nowP  = hvst.scope(env,clk,(teg,'nowP'))
prb_Iout  = hvst.scope(env,clk,(buckOut,'I'))
prb_Vout  = hvst.scope(env,clk,(buckOut,'V'))
prb_Vstor = hvst.scope(env,clk,(Cstor,'V'))
prb_Vbat  = hvst.scope(env,clk,(Cbat,'V'))
prb_Qstor = hvst.scope(env,clk,(Cstor,'Q'))
prb_Qbat  = hvst.scope(env,clk,(Cbat,'Q'))
prb_HdU   = hvst.scope(env,clk,(harvester,'dU'))
prb_BdU   = hvst.scope(env,clk,(buckOut,'dU'))
prb_Utot  = hvst.scope(env,clk,(harvester,'Ustored'))
prb_HdQ   = hvst.scope(env,clk,(harvester,'dQ'))

###################################################
# Run the simulation!
if stop_time == None:
    env.run()
else:
    env.run(until=stop_time)
# All done! mark end of time and finish the bq25570 state log
print('Time stop: @ %f' % env.now)
harvester.logState()

###################################################
# Plot the data collected by the scope probes above

fontsize='x-large'

plt.figure()  # plot state history
plt.plot(harvester.stateLog['time'], harvester.stateLog['data'], label='Hvst State')
plt.title('Hvst State', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('State', fontsize=fontsize)
plt.legend(fontsize=fontsize)

plt.figure()  # plot change in energy from TEG and load
plt.plot(prb_teg.time, prb_teg.data, label='teg P')
plt.plot(prb_Utot.time, prb_Utot.data, label='teg Utot')
plt.title('Energy', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Energy (J)', fontsize=fontsize)
plt.legend(fontsize=fontsize)

"""
plt.figure()  # plot change in energy from TEG and load
plt.plot(prb_nowP.time, prb_nowP.data, label='teg nowP')
plt.title('Energy', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Energy (J)', fontsize=fontsize)
plt.legend(fontsize=fontsize)
"""

"""
plt.figure()  # plot change in energy from TEG and load
plt.plot(prb_HdU.time, prb_HdU.data, label='Hvst dU')
plt.plot(prb_BdU.time, prb_BdU.data, label='Buck dU')
plt.plot(prb_Utot.time, list_m(prb_HdU.data,prb_BdU.data), label='Diff dU')
plt.title('delta Energy', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Energy (J)', fontsize=fontsize)
plt.legend(fontsize=fontsize)
"""

plt.figure()  # plot total voltage stored
plt.plot(prb_Vstor.time, prb_Vstor.data, label='Cstor V')
plt.plot(prb_Vbat.time, prb_Vbat.data, label='Cbat V')
plt.title('Cap V', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Volts', fontsize=fontsize)
plt.legend(fontsize=fontsize)

plt.figure()  # plot total current drawn by load
plt.plot(prb_Iout.time, prb_Iout.data, label='Iout')
plt.title('Load Current', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Current(a)', fontsize=fontsize)
plt.legend(fontsize=fontsize)

plt.figure()  # plot total current drawn by load
plt.plot(prb_Vout.time, prb_Vout.data, label='Vout')
plt.title('Output Voltage', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Volts (v)', fontsize=fontsize)
plt.legend(fontsize=fontsize)

"""
plt.figure()  # plot total charge stored
plt.plot(prb_Qstor.time, prb_Qstor.data, label='Cstor Q')
plt.title('Cstor Q', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Charge', fontsize=fontsize)
plt.legend(fontsize=fontsize)
"""

"""
plt.figure()  # plot change in cap charge
plt.plot(prb_HdQ.time, prb_HdQ.data, label='Hvst dQ')
plt.title('Cap Change of Charge', fontsize=fontsize)
plt.xlabel('Time (s)', fontsize=fontsize)
plt.ylabel('Charge (C)', fontsize=fontsize)
plt.legend(fontsize=fontsize)
"""

###################################################
###################################################
###################################################
