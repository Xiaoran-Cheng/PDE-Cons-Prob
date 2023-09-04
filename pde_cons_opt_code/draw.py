# import sys
# import os
# parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# current_dir = os.getcwd().replace("\\", "/")
# sys.path.append(parent_dir)

# from optim_sqp import SQP_Optim

# from Data import Data
# from NN import NN
# from Visualization import Visualization

# from jax import numpy as jnp
# from flax import linen as nn
# import jax.numpy as jnp
# import jax
# import numpy as np
# import pandas as pd



# beta = 30
# xgrid = 256
# nt = 100
# N=1000
# IC_M, pde_M, BC_M = 3,3,3                                             
# M = IC_M + pde_M + BC_M
# data_key_num, sample_key_num = 100,256
# x_min = 0
# x_max = 2*jnp.pi
# t_min = 0
# t_max = 1
# noise_level = 0.01                                                       
# nu = rho = 5
# system = "convection"

# NN_key_num = 345
# features = [50,50,50,50,1]                                               


# visual = Visualization(current_dir)

# def flatten_params(params):
#     flat_params_list, treedef = jax.tree_util.tree_flatten(params)
#     return np.concatenate([param.ravel( ) for param in flat_params_list], axis=0), treedef


# def unflatten_params(param_list, treedef):
#     param_groups = jnp.split(param_list, indices)
#     reshaped_params = [group.reshape(shape) for group, shape in zip(param_groups, shapes)]
#     return jax.tree_util.tree_unflatten(treedef, reshaped_params)


# activation = nn.tanh
# model = NN(features=features, activation=activation)
# Datas = Data(N, IC_M, pde_M, BC_M, xgrid, nt, x_min, x_max, t_min, t_max, beta, noise_level, nu, rho, system)
# data, ui = Datas.generate_data(data_key_num)
# pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi = Datas.sample_data(sample_key_num)
# eval_data, eval_ui = Datas.get_eval_data()
# color_bar_bounds = [eval_ui.min(), eval_ui.max()]
# params = model.init_params(NN_key_num=NN_key_num, data=data)

# shapes_and_sizes = [(p.shape, p.size) for p in jax.tree_util.tree_leaves(params)]
# shapes, sizes = zip(*shapes_and_sizes)
# indices = jnp.cumsum(jnp.array(sizes)[:-1])
# _, treedef = flatten_params(params)


# experiment_list = ['Pre_Train' ,"ALM", 'L2', "L2^2", 'SQP', 'ALP', 'ALM', 'L2', 'L2^2', 'PINN_1', 'PINN_10','PINN_100', 'PINN_1000']


# first_level = [ 'L2_pretrain_result',
#                 'with_pretrain_experiment_result',
#                 'with_pretrain_experiment_result',
#                 'with_pretrain_experiment_result',
#                 'with_pretrain_experiment_result',
#                 'with_pretrain_experiment_result',
#                 'without_pretrain_experiment_result',
#                 'without_pretrain_experiment_result',
#                 'without_pretrain_experiment_result',
#                 'without_pretrain_experiment_result',
#                 'without_pretrain_experiment_result',
#                 'without_pretrain_experiment_result',
#                 'without_pretrain_experiment_result']

# second_level = [ '', 
#                 'ALM_result',
#                  'L2^2_L2_result',
#                  'L2^2_L2_result',
#                  'SQP_result',
#                  'ALP_result',
#                  'aug_result',
#                  'L2^2_L2_result',
#                  'L2^2_L2_result',
#                  'PINN_experiment_penalty_1',
#                  'PINN_experiment_penalty_10',
#                  'PINN_experiment_penalty_100',
#                  'PINN_experiment_penalty_1000']

# third_level = [ 'params_303030_L2.csv',
#                 'params_Augmented_Lag_experiment.csv',
#                 'params_l2_Penalty_experiment.csv',
#                 'params_l2^2_Penalty_experiment.csv',
#                 'params_SQP_experiment.csv',
#                 'params_Pillo_Aug_Lag_experiment.csv',
#                 'params_Augmented_Lag_experiment.csv',
#                 'params_l2_Penalty_experiment.csv',
#                 'params_l2^2_Penalty_experiment.csv',
#                 'params_PINN_experiment_penalty_1.csv',
#                 'params_PINN_experiment_penalty_10.csv',
#                 'params_PINN_experiment_penalty_100.csv',
#                 'params_PINN_experiment_penalty_1000.csv']



# visual.heatmap(eval_data, eval_ui[0], "True_sol", experiment="True_sol", beta=beta, activation="", nt=nt, xgrid=xgrid, color_bar_bounds=color_bar_bounds, figure_type="True_sol")

# for first, second, third, experiment in zip(first_level, second_level, third_level, experiment_list):
#     params_path = os.path.join(current_dir, '303030', first, second, third)
#     params = pd.read_csv(params_path).values.flatten()
#     params = unflatten_params(params, treedef)
#     sqp_optim = SQP_Optim(model, params, beta, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui, N, eval_data, eval_ui, nu, rho, system)

#     absolute_error, l2_relative_error, eval_u_theta = \
#         sqp_optim.evaluation(params, eval_data, eval_ui[0])
        
#     visual.heatmap(eval_data, eval_u_theta, first, experiment=experiment, activation="", beta=beta, nt=nt, xgrid=xgrid, color_bar_bounds=color_bar_bounds, figure_type=experiment)





import sys
import os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
current_dir = os.getcwd()
sys.path.append(parent_dir)

from Data import Data
from NN import NN
from Visualization import Visualization

from jax import numpy as jnp
from flax import linen as nn
import jax.numpy as jnp
import jax
import pandas as pd
import numpy as np


dicts = {'params_Augmented_Lag_experiment.csv': "ALM",
         'params_l2^2_Penalty_experiment.csv': "L2^2",
         'params_l2_Penalty_experiment.csv': "L2",
         'params_Pillo_Aug_Lag_experiment.csv': "ALP",
         'params_SQP_experiment.csv': "SQP",
         'params_PINN_experiment_1.csv': "PINN_1",
         'params_PINN_experiment_10.csv': "PINN_10",
         'params_PINN_experiment_100.csv': "PINN_100",
         'params_PINN_experiment_1000.csv': "PINN_1000",
         "params_505050_L2.csv": "Pre_Train"
}

beta = 30
nu = 20
rho = 30

xgrid = 256
nt = 100
N=100
IC_M, pde_M, BC_M = 1,3,3                
M = IC_M + pde_M + BC_M
data_key_num, sample_key_num = 23312,952
x_min = 0
x_max = 2*jnp.pi
t_min = 0
t_max = 1
noise_level = 0.01                                     
system = "reaction"                                            #check

NN_key_num = 7654
features = [50,50,50,50,1]                      

visual = Visualization(current_dir)

def unflatten_params(param_list, treedef):
    param_groups = jnp.split(param_list, indices)
    reshaped_params = [group.reshape(shape) for group, shape in zip(param_groups, shapes)]
    return jax.tree_util.tree_unflatten(treedef, reshaped_params)

def flatten_params(params):
    flat_params_list, treedef = jax.tree_util.tree_flatten(params)
    return np.concatenate([param.ravel( ) for param in flat_params_list], axis=0), treedef


def get_params_dirs(problem):
    reaction_params_dirs = []
    reaction = os.path.join(current_dir, problem)
    for i in os.listdir(reaction):
        for j in os.listdir(os.path.join(reaction, i)):
            if "csv" in j:
                reaction_params_dirs.append(os.path.join(os.path.join(reaction, i), j))
    return reaction_params_dirs

activation = nn.tanh
activation_name = activation.__name__
model = NN(features=features, activation=activation)
Datas = Data(N, IC_M, pde_M, BC_M, xgrid, nt, x_min, x_max, t_min, t_max, beta, noise_level, nu, rho, system)
data, ui = Datas.generate_data(data_key_num)
eval_data, eval_ui = Datas.get_eval_data()
color_bar_bounds = [eval_ui.min(), eval_ui.max()]
params = model.init_params(NN_key_num=NN_key_num, data=data)
_, treedef = flatten_params(params)
shapes_and_sizes = [(p.shape, p.size) for p in jax.tree_util.tree_leaves(params)]
shapes, sizes = zip(*shapes_and_sizes)
indices = jnp.cumsum(jnp.array(sizes)[:-1])




for i in get_params_dirs(system):
    params = pd.read_csv(i).values.flatten()
    params = unflatten_params(params, treedef)
    eval_u_theta = model.u_theta(params=params, data=eval_data)
    pretrain_or_not_folder = os.path.basename(os.path.dirname(i))
    visual.heatmap(eval_data, eval_u_theta, pretrain_or_not_folder, experiment=dicts[os.path.basename(i)], nt=nt, xgrid=xgrid, color_bar_bounds=color_bar_bounds, figure_type=dicts[os.path.basename(i)])

visual.heatmap(eval_data, eval_ui[0], "True_sol", experiment="True_sol", nt=nt, xgrid=xgrid, color_bar_bounds=color_bar_bounds, figure_type = "True_sol")