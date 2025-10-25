# -*- coding: utf-8 -*-
"""
Created on Tue Oct  7 14:45:45 2025

@author: Marcos Cruz
"""


import logging
import pypsa
import pandas
import matplotlib.pyplot as plt
import numpy as np


logging.basicConfig(level=logging.ERROR)
pypsa.pf.logger.setLevel(logging.ERROR)


load_data = pandas.read_csv("grid_data_tutorial.csv")




def soccal (p,soc): # state of charge calculation
    #p is the battery power
    #soc is the state of charge

    minsoc = 20    #minimum state of charge
    maxsoc = 90   #maximum state of charge
    e = 0.95 #round trip efficiency
    cap = 1/30*100 #capacity 1/kWh * 100%
    
    
    socn = soc
    
    p = p*cap #normalise power with respect to capacity
    
    if p >0:
        soc = soc+p*e
        if soc >maxsoc:
            soc = maxsoc
            p = (maxsoc - socn)/e
            
    else:
        soc = soc+p/e
        
        if soc<minsoc:            
            soc = minsoc
            p = (minsoc-socn)*e
    
    socout = soc
    pout = p/cap
    
    return pout,socout


def Forecast_agent(hour):
    
    ld = pandas.read_csv("grid_data_tutorial.csv")
    price_data = ld["cost"]
    forecastprice = price_data.iloc[hour%24]
    
    return forecastprice


def DER_agent(price):
    
    der_p = 0
    if price<=4:
        der_p = 0
    else:
        der_p = 4

    return der_p

def ESS_agent(price,gen,load):

    p_action = 0
    if gen<load:
        if price>3:
            p_action = max(-4,gen-load) #discharge
   
    if gen>load:
        if price<5:
            p_action = min(4,gen-load) #charge
    

    return p_action

    
volt_response =[]
soc_record = []
pess_record = []
gen_record = []
load_record = []

# Circuit Definition
net = pypsa.Network()

r_line = 0.15 # ohms
x_line = 0.05 # ohms

vnom = 0.220 #kV

net.add("Bus", "Main_grid", v_nom = vnom)
net.add("Bus", "PCC", v_nom = vnom)
net.add("Bus", "Prosumer", v_nom = vnom)
net.add("Bus", "Consumer", v_nom = vnom)
net.add("Bus", "PV", v_nom = vnom)
net.add("Bus", "ESS", v_nom = vnom)



net.add("Line","line 0001", bus0 = "Prosumer", bus1 = "Consumer", x = 2*x_line, r = 2*r_line)
net.add("Line","line 0002", bus0 = "PCC", bus1 = "Consumer", x = 2*x_line, r = 2*r_line)
net.add("Line","line 0003", bus0 = "PV", bus1 = "Consumer", x = 4*x_line, r = 4*r_line)
net.add("Line","line 0004", bus0 = "ESS", bus1 = "PV", x = 1*x_line, r = 1*r_line)
net.add("Line","line 0005", bus0 = "Main_grid", bus1 = "PCC", x = 1*x_line, r = 1*r_line)


net.add("Generator","Gen_MG", bus = "Main_grid", control = "Slack")




#Data Definition
t = load_data["time"]
pv = load_data["generation"]
consumer_load = load_data["load"]



current_soc = 50
#Circuit Simulation
for i in range(t.size):
    f_price = Forecast_agent(i)
    
    
    net.add("Generator","Gen_PV", bus = "PV",\
        p_set = 0.001*pv[i],\
        control = "PQ",\
        overwrite = True) #MW
    
    net.add("Generator","Gen_DER", bus = "Prosumer",\
        p_set = 0.001*DER_agent(f_price),\
        control = "PQ",\
        overwrite = True) #MW
     
    net.add("Load", "Load_consumer", bus = "Consumer",\
        p_set = 0.001*consumer_load[i],\
        q_set = 0.0002*consumer_load[i],\
        overwrite= True) #MW and MVAR 

    action = ESS_agent(f_price,pv[i],consumer_load[i])
    
    [px,sx]= soccal(action*1,current_soc)
    current_soc = sx

    net.add("Load", "Battery", bus = "ESS",\
        p_set = 0.001*px,\
        overwrite= True) #MW and MVAR 


    net.pf() # power flow calculation
    volt_response.extend(net.buses_t.v_mag_pu.iloc[0,:].to_numpy())
    gen_record.extend(net.generators_t["p"].iloc[0,:].to_numpy())
    load_record.extend(net.loads_t["p"].iloc[0,:].to_numpy())
    
    pess_record.append(px)
    soc_record.append(sx)

gen_record = np.reshape(gen_record, (t.size,3))
load_record = np.reshape(load_record, (t.size,2))

# Plot voltage response
volt_response = np.reshape(volt_response, (t.size,6))

fig,ax = plt.subplots()
CS=ax.pcolormesh(volt_response.transpose()) 
cbar = fig.colorbar(CS)
plt.title("Voltage Amplitude (p. u.)")
plt.xlabel("Time (h)")
plt.ylabel("Bus")
plt.show()



