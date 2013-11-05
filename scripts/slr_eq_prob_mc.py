import sys
sys.path.append('../eq_stats')

import numpy as np
import pandas as pd
import eq_stats as eqs
import time
from joblib import Parallel, delayed

# problem setup

# read in fault data table
f = pd.read_csv('../data/lanf_stats.csv', index_col=0) 

# define some constants and parameters
n_eq_samp = 5e4 # number of earthquakes in time series
time_window = np.hstack( (1, np.arange(5, 105, step=5) ) ) # observation times
mc_iters = 1e3 # number of Monte Carlo iterations
mc_index = np.arange(mc_iters, dtype='int')
mc_cols = ['dip', 'Ddot'] + [t for t in time_window]
max_eq_slip = 15 #m
Mc = 7.64

# define frequency-magnitude distribution  not needed in this instance
#M_vec = np.linspace(5, Mc, num=1000)
#FM_vec = eqs.F(M=M_vec, Mc=Mc)

# load fault data and make dfs for each minimum search magnitude
slr_params = f.loc['s_lunggar']

slr = {}
min_M_list = [5, 5.5, 6, 6.5, 7, 7.5]

for MM in min_M_list:
    slr[MM] = pd.DataFrame(index=mc_index, columns=mc_cols, dtype='float')
    
    slr[MM].dip, slr_dip_frac = eqs.dip_rand_samp( slr_params['dip_deg'],
                                                  slr_params['dip_err_deg'],
                                                  mc_iters)
    
    slr[MM].Ddot = eqs.Ddot_rand_samp(slr_params['slip_rate_mm_a'],
                                      slr_params['sr_err_mm_a'], mc_iters)

# define function to calculate probabilities for each iteration
# function is defined here so it can access all variables
def calc_row_probs(df, index):
    ss = df.iloc[index]
    # Calculate maximum EQ size based on maximum mean slip (D)
    max_Mo = eqs.calc_Mo_from_fault_params(L=slr_params['L_km'], 
                                           z=slr_params['z_km'], 
                                           dip=ss['dip'], D=max_eq_slip)
    max_M = eqs.calc_M_from_Mo(max_Mo)
    
    # Generate EQ sample/sequence from F(M) dist.
    m_vec = np.linspace(5, max_M, num=1000)
    fm_vec = eqs.F(m_vec, Mc=Mc)
    M_samp = eqs.sample_from_pdf(m_vec, fm_vec, n_eq_samp)
    Mo_samp = eqs.calc_Mo_from_M(M_samp)
    
    # Make time series of earthquakes, including no eq years
    recur_int = eqs.calc_recurrence_interval(Mo=Mo_samp, dip=ss['dip'],
                                             slip_rate=ss['Ddot'],
                                             L=slr_params['L_km'],
                                             z=slr_params['z_km'])
    cum_yrs = eqs.calc_cumulative_yrs(recur_int)
    eq_series = eqs.make_eq_time_series(M_samp, cum_yrs)
    
    # calculate probability of observing EQ in time_window
    for t in time_window:
        ss[t] = ( eqs.get_prob_above_val_in_window(eq_series, MM, t)
                 * slr_dip_frac)
    return ss

# run script
for MM in min_M_list:
    t_in = time.time()
    ss_list = Parallel(n_jobs=-2)(delayed( calc_row_probs)(slr[MM], ii)
                                  for ii in mc_index)
    for n_row, ser in enumerate(ss_list):
        ind = ser.index
        slr[MM].iloc[n_row][list(ind)] = ser.values
        
    print 'done with', MM, 'in', time.time()-t_in, 's'

print slr[MM].head()