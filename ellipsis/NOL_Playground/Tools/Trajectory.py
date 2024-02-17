# Lejun Shen, IACSS, 2017
# Measurement and Performance Evaluation of Lob Technique using Aerodynamic Model In Badminton Matches
import matplotlib.pyplot as plt
import math
import sys
import os
import numpy as np
from scipy.integrate import solve_ivp
import seaborn as sns
from itertools import product
sns.set()
DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(DIRNAME)
sys.path.append(f"{ROOTDIR}/lib")
#14-40 ~ v
Velocity = np.arange(14, 30, 1)
#0-39 ~ incline
Incline = np.arange(-16, 20, 1)

def physics_predict3d(starting_point, limit, theta , Vz, Vxy, Dir, flight_time=5, touch_target_cut=True, alpha=0.21520, g=9.8):
    initial_velocity = [math.sin(theta)*Vxy,math.cos(theta)*Vxy,Vz]
    
    # biar arahnya bener (kalau arah starting point ke point yg ditravel beda, speednya yg hrsnya negatif malah ke positif, harus diflip)
    if(Dir[0] != initial_velocity[0]/abs(initial_velocity[0])): initial_velocity[0] *= -1
    if(Dir[1] != initial_velocity[1]/abs(initial_velocity[1])): initial_velocity[1] *= -1


    traj = solve_ivp(lambda t, y: bm_ball(t, y, alpha=alpha, g=g), [0, flight_time], np.concatenate((starting_point[:3], initial_velocity)), t_eval = np.arange(0, flight_time, 0.033)) # traj.t traj.y
    xyz = np.swapaxes(traj.y[:3,:], 0, 1) # shape: (N points, 3)
    t = np.expand_dims(traj.t,axis=1) # shape: (N points, 1)
    trajectories = np.concatenate((xyz, t),axis=1) # shape: (N points, 4)
    # Cut the part under the ground
    if touch_target_cut:
        for i in range(trajectories.shape[0]-1):
            # limit for x, y, and z (which is the original trajectory's coordinates)
            if Dir[0] == -1 and trajectories[i+1,0] <= limit[0]:
                trajectories = trajectories[:i+1,:]
                break
            if Dir[0] == 1 and trajectories[i+1,0] > limit[0]:
                trajectories = trajectories[:i+1,:]
                break
            if Dir[1] == -1 and trajectories[i+1,1] <= limit[1]:
                trajectories = trajectories[:i+1,:]
                break
            if Dir[1] == 1 and trajectories[i+1,1] > limit[1]:
                trajectories = trajectories[:i+1,:]
                break
            if trajectories[i,2] >= limit[2] and trajectories[i+1,2] <= limit[2]:
                trajectories = trajectories[:i+1,:]
                break
    
    return trajectories # shape: (N points, 4) , include input two Points

def find_traj(starting_point, end_point, getVnI = False):
    combs = [(math.sin(math.radians(i))*v,math.cos(math.radians(i))*v) for v,i in product(Velocity,Incline)]
    Dist = end_point[:2]-starting_point[:2]
    theta = math.atan(Dist[0]/Dist[1])
    
    Dir = Dist/abs(Dist)
    print(theta)
    # print(Dir)
    min_dist = 99
    for Vz,Vxy in combs:
        # print(Dir*Vxy)
        traj = physics_predict3d(starting_point, end_point, -theta, Vz, Vxy, Dir)
        pred_end = traj[-1]
        dist = math.sqrt((pred_end[0]-end_point[0])**2 + (pred_end[1]-end_point[1])**2 + (pred_end[2]-end_point[2])**2)
        
        if(dist < min_dist):
            min_dist = dist
            min_traj = traj
            min_vz = Vz
            min_vxy = Vxy
    
    index = combs.index((min_vz,min_vxy))
    v = Velocity[int(index/36)]
    i = Incline[index%36]

    if(theta/abs(theta) == -1):  
        v += 1
    p = round(theta * 180 / math.pi)
    if(theta/abs(theta) == 1):
      p = round(theta * 180 / math.pi) - 1
    
    if((theta * 180 / math.pi > -1 )and (theta * 180 / math.pi < 1 )):
        p  = 0
        
    if not getVnI:        
        return min_traj

    # p = round(theta * 180 / math.pi)
    print(round(v/160 * 100))
    return v,i,p


def bm_ball(t,x,alpha=0.21520, g=9.8):
    # velocity
    v = math.sqrt(x[3]**2+x[4]**2+x[5]**2)
    # ordinary differential equations (3)
    xdot = [ x[3], x[4], x[5], -alpha*x[3]*v, -alpha*x[4]*v, -g-alpha*x[5]*v]
    return xdot


if __name__ == '__main__':
    # # test physics_predict3d function
    # #===========case 1==========
    # p1 = np.array([1.166179244,	-2.050772068, 1.491008632,  2.033333333])
    # p2 = np.array([-2.129169792, -3.708546295, 0.095679186, 2.95])
    #===========case 2==========
    # p1 = np.array([0.0,0.0,0.0])
    # p2 = np.array([-0.1339802542688704,-1.904269790408479,2.588970620250396])
    #===========case 3==========
    p1 = np.array([0.0,-2.25,1.5])
    p2 = np.array([-0.1346621918318704,1.312591880227425,1.9366031577138247])
    # a = physics_predict3d(p1, p2)
    # print(a)
    # print([x for x in product(Velocity,Incline)])
    import time
    curtime = time.time()
    print(find_traj(p1,p2,False))
    print(find_traj(p1,p2,True))
    print(time.time() - curtime)

    sys.exit(1)

