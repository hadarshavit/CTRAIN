import torch

from CTRAIN.bound import bound_ibp, bound_crown_ibp
from CTRAIN.train.certified.losses import get_loss_from_bounds

def get_crown_ibp_loss(hardened_model, ptb, data, target, n_classes, criterion, beta, return_bounds=False, return_stats=True):
    """
    Compute the CROWN-IBP loss.
    
    Parameters:
        hardened_model (auto_LiRPA.BoundedModule): The bounded model to be trained.
        ptb (autoLiRPA.PerturbationLpNorm): The perturbation applied to the input data.
        data (torch.Tensor): The input data.
        target (torch.Tensor): The target labels.
        n_classes (int): The number of classes in the classification task.
        criterion (callable): The loss function to be used.
        beta (float): The interpolation parameter between CROWN_IBP and IBP bounds.
        return_bounds (bool, optional): If True, return the lower bounds. Default is False.
        return_stats (bool, optional): If True, return the robust error statistics. Default is True.
    
    Returns:
        (tuple): A tuple containing the certified loss. If return_bounds is True, the tuple also contains the lower bounds.
            If return_stats is True, the tuple also contains the robust error statistics.
    """
    ilb, iub = bound_ibp(
        model=hardened_model,
        ptb=ptb,
        data=data,
        target=target,
        n_classes=n_classes,
        bound_upper=False
    )
    if beta < 1e-5:
        lb = ilb
    else:
        # Attention: We have to reuse the input here. Otherwise the memory requirements become too large!
        # Input is reused from above bound_ibp call!
        clb, cub = bound_crown_ibp(
            model=hardened_model,
            ptb=ptb,
            data=data,
            target=target,
            n_classes=n_classes,
            reuse_input=True,
            bound_upper=False
        )
        
        lb = clb * beta + ilb * (1 - beta)

    certified_loss = get_loss_from_bounds(lb, criterion)
    
    return_tuple = (certified_loss,)
    
    if return_bounds:
        return_tuple = return_tuple + (lb, None)
    if return_stats:
        robust_err = torch.sum((lb < 0).any(dim=1)).item() / data.size(0)
        return_tuple = return_tuple + (robust_err,)
    
    return return_tuple