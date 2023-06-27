import sys
import os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

from Transport_eq import Transport_eq

from jax import numpy as jnp
from jax import jacfwd, grad
import pandas as pd
from flax.core.frozen_dict import unfreeze



class HanPenalty:
    def __init__(self, model, data, sample_data, IC_sample_data, \
            ui, beta, N, M):
        self.model = model
        self.beta = beta
        self.data = data
        self.sample_data = sample_data
        self.IC_sample_data = IC_sample_data
        self.ui = ui
        self.N = N
        self.M = M


    def l_k(self, params):
        u_theta = self.model.u_theta(params=params, data=self.data)
        return jnp.square(jnp.linalg.norm(u_theta - self.ui, ord=2))
    

    def IC_cons(self, params):
        u_theta = self.model.u_theta(params=params, data=self.IC_sample_data)
        return Transport_eq(beta=self.beta).solution(\
            self.IC_sample_data[:,0], self.IC_sample_data[:,1]) - u_theta
    
    
    def pde_cons(self, params):
        grad_x = jacfwd(self.model.u_theta, 1)(params, self.sample_data)
        return Transport_eq(beta=self.beta).pde(jnp.diag(grad_x[:,:,0]),\
            jnp.diag(grad_x[:,:,1]))
    

    def eq_cons(self, params):
        return jnp.concatenate([self.IC_cons(params), self.pde_cons(params)])


    def L(self, params, mul):
        return self.l_k(params) + self.eq_cons(params) @ mul
    

    def loss(self, params_mul, penalty_param):
        params = params_mul[0]
        mul = params_mul[1]
        return self.L(params, mul) + 0.5 * penalty_param * \
        pd.DataFrame.from_dict(unfreeze(jacfwd(self.L, 0)(params, mul)["params"])).\
            applymap(lambda x: jnp.linalg.norm(x,ord=2)).values.sum()
    
