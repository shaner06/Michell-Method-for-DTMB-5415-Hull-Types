import numpy as np
from HullParameterization import Hull_Parameterization as HP

v = np.array([
     6.171164,0.551634,0.411168,0.132064,0.0729198,0.522474,0.551111,0.114611,12.504747,0.575244,0.927874,-3.053316,3.571634,0.588811,0.405271,-0.696478,0.35302,-1.20647,1.505512,0.320019,0,0,0.276896,0.439108,0.182253,0.867846,-0.03103,8.107803,0.104768,0.411388,0.180543,0,0,1e-05,0.001,16,-0.75,0.9,0.5,0.01,1,0.5,0.01,0.999,1e-08
    # type the 45 inout numbers here, comma between each
], dtype=np.float64)

print(len(v))   # must print 45 if successful

Hull = HP(v)
mesh = Hull.gen_stl(NUM_WL=100, PointsPerWL=800,
                    bit_AddTransom=1, bit_AddDeckLid=1,
                    namepath='./my_hull')