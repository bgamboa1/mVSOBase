import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from pandas import datetime

pv_data = pd.read_csv('pvwatts_hourly.csv',
                      header=0, parse_dates=[0],
                      index_col=0)

print(pv_data.head())

x = np.linspace(0, 8760, num=8760, endpoint=True)

y = pv_data['W_ac']

f = interp1d(x, y)

f2 = interp1d(x, y, kind='cubic')

xnew = np.linspace(0, 8760, num=35040, endpoint=True)

plt.plot(x, y, 'o', xnew, f(xnew), '-', xnew, f2(xnew), 'o')

pv_interp = f2(xnew)

data = pv_interp

columns = ['W_ac']

pvdf = pd.DataFrame(pv_interp, columns=columns)

pvdf[pvdf < 2] = 0

print(pvdf)

pvdf.to_csv(path_or_buf='pv_data.csv', encoding='utf-8')
