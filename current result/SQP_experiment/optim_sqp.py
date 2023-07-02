import sys
import os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

from Transport_eq import Transport_eq

from jax import numpy as jnp
from jax import jacfwd
from tqdm.notebook import tqdm
import numpy as np
import pandas as pd
from flax.core.frozen_dict import FrozenDict, unfreeze
from jaxopt import BacktrackingLineSearch, HagerZhangLineSearch



class OptimComponents:
    def __init__(self, model, data, sample_data, IC_sample_data, ui, beta):
        self.model = model
        self.beta = beta
        self.data = data
        self.sample_data = sample_data
        self.IC_sample_data = IC_sample_data
        self.ui = ui


    def obj(self, params):
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
    

    def get_grads(self, params):
        gra_obj = jacfwd(self.obj, 0)(params)
        gra_eq_cons = jacfwd(self.eq_cons, 0)(params)
        # Hlag = hessian(self.lag, 0)(params, mul)
        return gra_obj, gra_eq_cons
    
        
        
class SQP_Optim:
    def __init__(self, model, optim_components, qp, feature, group_labels, hessian_param, M, params) -> None:
        self.model = model
        self.optim_components = optim_components
        self.qp = qp
        self.feature = feature
        self.group_labels = group_labels
        self.hessian_param = hessian_param
        self.M = M
        self.layer_names = params["params"].keys()


    # def get_shapes_size(self, params):
    #     shapes = pd.DataFrame.from_dict(unfreeze(params["params"])).applymap(lambda x: x.shape).values.flatten()
    #     sizes = [np.prod(shape) for shape in shapes]
    #     return shapes, sizes
    

    def flat_single_dict(self, dicts):
        return np.concatenate(pd.DataFrame.from_dict(unfreeze(dicts["params"])).\
                        applymap(lambda x: x.flatten()).values.flatten())
    

    def flat_multi_dict(self, dicts):
        return np.concatenate(pd.DataFrame.from_dict(\
                unfreeze(dicts['params'])).\
                    apply(lambda x: x.explode()).set_index([self.group_labels]).\
                        sort_index().applymap(lambda x: x.flatten()).values.flatten())
    

    # def get_direction(self, flatted_gra_obj, flatted_gra_eq_cons, eq_cons):
    #     Q = self.hessiam_param * jnp.identity(flatted_gra_obj.shape[0])
    #     c = flatted_gra_obj
    #     A = jnp.array(jnp.split(flatted_gra_eq_cons, 2*self.M))
    #     b = -eq_cons
    #     flatted_delta_params = self.qp.run(params_obj=(Q, c), params_eq=(A, b)).params.primal
    #     return flatted_delta_params
    

    def get_recovered_dict(self, flatted_target, shapes, sizes):
            subarrays = np.split(flatted_target, np.cumsum(sizes)[:-1])
            reshaped_arrays = [subarray.reshape(shape) for subarray, shape in zip(subarrays, shapes)]
            flatted_target_df = pd.DataFrame(np.array(reshaped_arrays, dtype=object).\
                        reshape(2,len(self.feature))).applymap(lambda x: x)
            flatted_target_df.columns = self.layer_names
            flatted_target_df.index = ["bias", "kernel"]
            flatted_target_df.sort_index(ascending=False, inplace=True)
            recovered_target = FrozenDict({"params": flatted_target_df.to_dict()})
            return recovered_target
    

    # def get_step_size(self, maxiter, condition, decrease_factor, params, delta_params, current_obj, gra_obj, init_stepsize):
    #         ls = BacktrackingLineSearch(fun=self.optim_components.obj, maxiter=maxiter, condition=condition,
    #                                     decrease_factor=decrease_factor)
    #         # ls = HagerZhangLineSearch(fun=self.optim_components.obj)
    #         stepsize, _ = ls.run(init_stepsize=init_stepsize, params=params,
    #                                 descent_direction=delta_params,
    #                                 value=current_obj, grad=gra_obj)
    #         return stepsize


    def SQP_optim(self, params, num_iter, maxiter, condition, decrease_factor, init_stepsize, line_search_tol):
        obj_list = []
        shapes = pd.DataFrame.from_dict(unfreeze(params["params"])).applymap(lambda x: x.shape).values.flatten()
        sizes = [np.prod(shape) for shape in shapes]
        for _ in tqdm(range(num_iter)):
            gra_obj, gra_eq_cons = self.optim_components.get_grads(params=params)
            eq_cons = self.optim_components.eq_cons(params=params)
            current_obj = self.optim_components.obj(params=params)

            flatted_gra_obj = self.flat_single_dict(gra_obj)
            flatted_current_params = self.flat_single_dict(params)
            flatted_gra_eq_cons = self.flat_multi_dict(gra_eq_cons)
            


            # flatted_delta_params = self.get_direction(flatted_gra_obj, flatted_gra_eq_cons, eq_cons)

            Q = self.hessian_param * jnp.identity(flatted_gra_obj.shape[0])
            c = flatted_gra_obj
            A = jnp.array(jnp.split(flatted_gra_eq_cons, 2*self.M))
            b = -eq_cons
            flatted_delta_params = self.qp.run(params_obj=(Q, c), params_eq=(A, b)).params.primal



            delta_params = self.get_recovered_dict(flatted_delta_params, shapes, sizes)

            # stepsize = self.get_step_size(maxiter=maxiter, condition=condition, decrease_factor=decrease_factor, \
            #             params=params, delta_params=delta_params, current_obj=current_obj, gra_obj=gra_obj, init_stepsize=init_stepsize)
            
            # ls = BacktrackingLineSearch(fun=self.optim_components.obj, maxiter=maxiter, condition=condition,
            #                             decrease_factor=decrease_factor)
            # # ls = HagerZhangLineSearch(fun=self.optim_components.obj)
            # stepsize, _ = ls.run(init_stepsize=init_stepsize, params=params,
            #                         descent_direction=delta_params,
            #                         value=current_obj, grad=gra_obj)
            ls = BacktrackingLineSearch(fun=self.optim_components.obj, maxiter=maxiter, condition=condition,
                                        decrease_factor=decrease_factor, tol=line_search_tol)
            stepsize, _ = ls.run(init_stepsize=init_stepsize, params=params,
                                    descent_direction=delta_params,
                                            value=current_obj, grad=gra_obj)



            flatted_updated_params = stepsize * flatted_delta_params + flatted_current_params
            params = self.get_recovered_dict(flatted_updated_params, shapes, sizes)
            obj_list.append(self.optim_components.obj(params))
        return params, obj_list
        

    def evaluation(self, params, N, data, ui):
        u_theta = self.model.u_theta(params = params, data=data)
        absolute_error = 1/N * jnp.linalg.norm(u_theta-ui)
        l2_relative_error = 1/N * jnp.linalg.norm((u_theta-ui)/ui)
        return absolute_error, l2_relative_error, u_theta
 