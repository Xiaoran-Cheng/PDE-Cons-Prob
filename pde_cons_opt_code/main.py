import time
start_time = time.time()

import sys
import os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
current_dir = os.getcwd().replace("\\", "/")
sys.path.append(parent_dir)

# from jax.config import config
# config.update("jax_enable_x64", True)

from optim_PINN import PINN
# from optim_l1_penalty import l1Penalty
from optim_l2_penalty import l2Penalty
# from optim_linfinity_penalty import linfinityPenalty
from optim_aug_lag import AugLag
# from optim_pillo_penalty import PilloPenalty
# from optim_new_aug_lag import NewAugLag
# from optim_fletcher_penalty import FletcherPenalty
from optim_pillo_aug_lag import PilloAugLag
from optim_sqp import SQP_Optim

from Data import Data
from NN import NN
from Visualization import Visualization
from uncons_opt import Optim
from pre_train import PreTrain

from jax import random
import pandas as pd
from jax import numpy as jnp
from flax import linen as nn
import jax.numpy as jnp
import jaxlib.xla_extension as xla
import jaxopt
from tqdm import tqdm
from scipy.optimize import BFGS, SR1
import jax
import numpy as np
import pandas as pd


#######################################config for data#######################################
Pre_Train = False
beta = 30
xgrid = 256
nt = 100
N=1000
IC_M, pde_M, BC_M = 3,3,3
M = IC_M + pde_M + BC_M
data_key_num, sample_key_num = 100,256
x_min = 0
x_max = 2*jnp.pi
t_min = 0
t_max = 1
####################################### config for data #######################################

####################################### config for NN #######################################
NN_key_num = 345
features = [50,50,50,50,1]
###################################### config for NN #######################################

####################################### config for unconstrained optim #######################################
LBFGS_maxiter = 50000
max_iter_train = 10

penalty_param_update_factor = 5
init_penalty_param = 1
panalty_param_upper_bound = 5**10

init_penalty_param_mu = 10**6
init_penalty_param_v = 10**-5

LBFGS_gtol = 1e-9
LBFGS_ftol = 1e-9

init_mul = jnp.zeros(M)

pretrain_maxiter = LBFGS_maxiter
pretrain_gtol = LBFGS_gtol
pretrain_ftol = LBFGS_ftol
####################################### config for unconstrained optim #######################################


####################################### visualization #######################################
visual = Visualization(current_dir)
####################################### visualization #######################################


####################################### config for SQP #######################################
sqp_maxiter = 1000000000
sqp_hessian = SR1()
sqp_gtol = 1e-8
sqp_xtol = 1e-8
sqp_initial_constr_penalty = 0.05
sqp_initial_tr_radius = 1
####################################### config for SQP #######################################

def flatten_params(params):
    flat_params_list, treedef = jax.tree_util.tree_flatten(params)
    return np.concatenate([param.ravel( ) for param in flat_params_list], axis=0), treedef


def unflatten_params(param_list, treedef):
    param_groups = jnp.split(param_list, indices)
    reshaped_params = [group.reshape(shape) for group, shape in zip(param_groups, shapes)]
    return jax.tree_util.tree_unflatten(treedef, reshaped_params)

activation_input = "tanh"

if activation_input == "sin":
    activation = jnp.sin
elif activation_input == "tanh":
    activation = nn.tanh
elif activation_input == "cos":
    activation = jnp.cos
elif activation_input == "identity":
    def identity(x):
        return x
    activation = identity

activation_name = activation.__name__
model = NN(features=features, activation=activation)
absolute_error_list = []
l2_relative_error_list = []
Datas = Data(N, IC_M, pde_M, BC_M, xgrid, nt, x_min, x_max, t_min, t_max, beta)
data, ui = Datas.generate_data(data_key_num)
pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi = Datas.sample_data(sample_key_num)
eval_data, eval_ui = Datas.get_eval_data()
params = model.init_params(NN_key_num=NN_key_num, data=data)
if Pre_Train:
    pretrain = PreTrain(model, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, beta, [])
    params = pretrain.update(params, pretrain_maxiter, pretrain_gtol, pretrain_ftol)
    absolute_error, l2_relative_error, eval_u_theta = pretrain.evaluation(\
                                params, eval_data, eval_ui[0])
    print("absolute_error: " + str(absolute_error))
    print("l2_relative_error: " + str(l2_relative_error))
    print("pretrain_loss_list: " + str(pretrain.pretrain_loss_list[-1]))
    visual.line_graph(pretrain.pretrain_loss_list, "Pre_Train_Loss", experiment='Pre_Train', activation=activation_name, beta=beta)
    visual.line_graph(eval_u_theta, "u_theta_line", experiment="Pre-Train", activation=activation_name, beta=beta)
    visual.heatmap(eval_data, eval_u_theta, "u_theta_heatmap", experiment='Pre_Train', activation=activation_name, beta=beta, nt=nt, xgrid=xgrid)
    flat_params, treedef = flatten_params(params)
    pd.DataFrame(flat_params, columns=['params']).to_csv("params.csv", index=False)

shapes_and_sizes = [(p.shape, p.size) for p in jax.tree_util.tree_leaves(params)]
shapes, sizes = zip(*shapes_and_sizes)
indices = jnp.cumsum(jnp.array(sizes)[:-1])
_, treedef = flatten_params(params)


for experiment in ['PINN_experiment', 
                    'l2_Penalty_experiment', 
                    'Augmented_Lag_experiment',
                    'Pillo_Aug_Lag_experiment',
                    'SQP_experiment']:

    #############
    params = pd.read_csv("params.csv")
    params = params.values.flatten()
    params = unflatten_params(params, treedef)
    params_mul = {"params": params, "mul":init_mul}
    #############

    penalty_param = init_penalty_param
    penalty_param_v = init_penalty_param_v
    penalty_param_mu = init_penalty_param_mu
    mul = init_mul
    error_df_list = []
    if experiment == "SQP_experiment":
        loss_values = []
        eq_cons_loss_values = []
        kkt_residual = []
        sqp_optim = SQP_Optim(model, params, beta, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui, N)
        # sqp_optim = SQP_Optim(model, params, beta, data, pde_sample_data, IC_sample_data, ui, N)
        params = sqp_optim.SQP_optim(params, loss_values, eq_cons_loss_values, kkt_residual, sqp_maxiter, sqp_hessian, sqp_gtol, sqp_xtol, sqp_initial_constr_penalty, sqp_initial_tr_radius)
        total_l_k_loss_list = [i.item() for i in loss_values if isinstance(i, xla.ArrayImpl)]
        total_eq_cons_loss_list = [i.item() for i in eq_cons_loss_values if isinstance(i, xla.ArrayImpl)]
        kkt_residual_list = [i.item() for i in kkt_residual if isinstance(i, xla.ArrayImpl)]
        absolute_error, l2_relative_error, eval_u_theta = \
            sqp_optim.evaluation(params, eval_data, eval_ui[0])
        
    else:
        if experiment == "PINN_experiment":
            loss = PINN(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
                        N)
        # elif experiment == "l1_Penalty_experiment":
        #     loss = l1Penalty(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
        #                 N)
        elif experiment == "l2_Penalty_experiment":
            loss = l2Penalty(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
                        N)
        # elif experiment == "linfinity_Penalty_experiment":
        #     loss = linfinityPenalty(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
        #                 N)
        elif experiment == "Augmented_Lag_experiment":
            loss = AugLag(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
                        N)
        # elif experiment == "Pillo_Penalty_experiment":
        #     loss = PilloPenalty(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
        #                 N, M)
        # elif experiment == "New_Augmented_Lag_experiment":
        #     loss = NewAugLag(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
        #                 N, M)
        # elif experiment == "Fletcher_Penalty_experiment":
        #     loss = FletcherPenalty(model, data, pde_sample_data, IC_sample_data, ui[0], beta, \
        #                 N)
        elif experiment == "Pillo_Aug_Lag_experiment":
            loss = PilloAugLag(model, data, pde_sample_data, IC_sample_data, BC_sample_data_zero, BC_sample_data_2pi, ui[0], beta, \
                        N)
        
        total_loss_list, total_eq_cons_loss_list, total_l_k_loss_list = [], [], []
        if experiment == "Augmented_Lag_experiment":
            def callback_func(params):
                total_loss_list.append(loss.loss(params, mul, penalty_param).item())
                total_l_k_loss_list.append(loss.l_k(params).item())
                total_eq_cons_loss_list.append(jnp.square(jnp.linalg.norm(loss.eq_cons(params), ord=2)).item())
        elif experiment == "Pillo_Aug_Lag_experiment":
            def callback_func(params_mul):
                params = params_mul['params']
                total_loss_list.append(loss.loss(params_mul, penalty_param_mu, penalty_param_v).item())
                total_l_k_loss_list.append(loss.l_k(params).item())
                total_eq_cons_loss_list.append(jnp.square(jnp.linalg.norm(loss.eq_cons(params), ord=2)).item())
        else:
            def callback_func(params):
                total_loss_list.append(loss.loss(params, penalty_param).item())
                total_l_k_loss_list.append(loss.l_k(params).item())
                total_eq_cons_loss_list.append(jnp.square(jnp.linalg.norm(loss.eq_cons(params), ord=2)).item())

        LBFGS_opt = jaxopt.ScipyMinimize(method='L-BFGS-B', \
                        fun=loss.loss, \
                        maxiter=LBFGS_maxiter, \
                        options={'gtol': LBFGS_gtol, 'ftol': LBFGS_ftol}, \
                        callback=callback_func)

        optim = Optim(model, loss)
        for _ in tqdm(range(max_iter_train)):
            params, params_mul, eq_cons = \
                optim.update(params, penalty_param, experiment, \
                                    mul, params_mul, \
                                    penalty_param_mu, \
                                    penalty_param_v, LBFGS_opt)

            if experiment == "Augmented_Lag_experiment":
                mul = mul + penalty_param * 2 * eq_cons
            if penalty_param <= panalty_param_upper_bound and experiment != "Pillo_Aug_Lag_experiment":
                penalty_param = penalty_param_update_factor * penalty_param
            if experiment == "Pillo_Aug_Lag_experiment" and penalty_param_mu <= panalty_param_upper_bound:
                penalty_param_mu = penalty_param_update_factor * penalty_param_mu
            # if experiment == "Pillo_Aug_Lag_experiment" and penalty_param_v >= 1/panalty_param_upper_bound:
            #     penalty_param_v = (1/penalty_param_update_factor) * penalty_param_v
            if experiment == "Pillo_Aug_Lag_experiment":
                print("penalty_param_mu: ", str(penalty_param_mu), 'penalty_param_v: ', str(penalty_param_v))
            else:
                print("penalty_param: ", str(penalty_param))

            print("Number of iterations:", str(len(total_loss_list)))

        absolute_error, l2_relative_error, eval_u_theta = optim.evaluation(\
                                        params, eval_data, eval_ui[0])
    
    # ###############
    # flat_params, treedef = flatten_params(params)
    # pd.DataFrame(flat_params, columns=['params']).to_csv("params.csv", index=False)
    # ###############

    if experiment != "SQP_experiment":
        visual.line_graph(total_loss_list, "Total_Loss", experiment=experiment, activation=activation_name, beta=beta)
    visual.line_graph(total_eq_cons_loss_list, "Total_eq_cons_Loss", experiment=experiment, activation=activation_name, beta=beta)
    visual.line_graph(total_l_k_loss_list, "Total_l_k_Loss", experiment=experiment, activation=activation_name, beta=beta)
    if experiment == "SQP_experiment":
        visual.line_graph(kkt_residual_list, "KKT_residual", experiment=experiment, activation=activation_name, beta=beta)
    visual.line_graph(eval_ui[0], "True_sol_line", experiment="", activation="", beta=beta)
    visual.line_graph(eval_u_theta, "u_theta_line", experiment=experiment, activation=activation_name, beta=beta)
    visual.heatmap(eval_data, eval_ui[0], "True_sol_heatmap", experiment="", beta=beta, activation="", nt=nt, xgrid=xgrid)
    visual.heatmap(eval_data, eval_u_theta, "u_theta_heatmap", experiment=experiment, activation=activation_name, beta=beta, nt=nt, xgrid=xgrid)
    absolute_error_list.append(absolute_error)
    l2_relative_error_list.append(l2_relative_error)
    if experiment != "SQP_experiment":
        print("last loss: "+str(total_loss_list[-1]))
    if experiment == "SQP_experiment":
        print("last KKT residual: " + str(kkt_residual_list[-1]))
    print("absolute_error: " + str(absolute_error))
    print("l2_relative_error: " + str(l2_relative_error))
    print("total_l_k_loss_list: " + str(total_l_k_loss_list[-1]))
    print("total_eq_cons_loss_list: " + str(total_eq_cons_loss_list[-1]))
    error_df = pd.DataFrame({'absolute_error': absolute_error_list, \
                            'l2_relative_error': l2_relative_error_list}).astype(float)
    error_df["activation"] = activation_name
    error_df["experiment"] = experiment
    error_df['Beta'] = beta
    error_df_list.append(error_df)
    folder_path = "{current_dir}/result/error".format(current_dir=current_dir)

pd.concat(error_df_list).to_csv(folder_path+".csv", index=False)
end_time = time.time()
print(f"Execution Time: {(end_time - start_time)/60} minutes")

