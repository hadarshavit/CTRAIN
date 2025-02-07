import torch
import torch.nn as nn


def get_l1_reg(model, device='cuda'):
    """
    Calculate the L1 regularization loss for a given model.

    This function computes the L1 regularization loss by summing the absolute values
    of the weights of all Linear and Convolutional layers in the model.

    Args:
        model (torch.nn.Module): The neural network model to regularize. IMPORTANT: Don't pass the bounded model here.
        device (str, optional): The device to perform the computation on. Default is 'cuda'.

    Returns:
        (torch.Tensor): The L1 regularization loss.
    """
    loss = torch.zeros(()).to(device)
    # only regularise Linear and Convolutional layers
    for module in model.modules():
        if isinstance(module, nn.Linear):
            loss += torch.abs(module.weight).sum()
        elif isinstance(module, nn.Conv2d):
            loss += torch.abs(module.weight).sum()
    return loss