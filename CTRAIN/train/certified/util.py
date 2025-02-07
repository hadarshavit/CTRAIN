import copy
import types
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from auto_LiRPA.bound_general import BoundedModule

from auto_LiRPA.operators.normalization import BoundBatchNormalization

from auto_LiRPA.operators.solver_utils import grb

from auto_LiRPA.linear_bound import LinearBound

from auto_LiRPA.operators.constant import BoundConstant

from auto_LiRPA.operators.leaf import BoundParams

from auto_LiRPA.patches import Patches, inplace_unfold

from auto_LiRPA.operators.base import Interval


def split_network(model, block_sizes, network_input, device):
    """
    Splits a neural network model into smaller sequential blocks based on specified block sizes. Needed for TAPS/STAPS.
    Args:
        model (torch.nn.Module): The neural network model to be split.
        block_sizes (list of int): A list of integers specifying the sizes of each block.
        network_input (torch.Tensor): The input tensor to the network.
        device (torch.device): The device to which the tensors should be moved (e.g., 'cpu' or 'cuda').
    Returns:
        list of torch.nn.Sequential: A list of sequential blocks representing the split network.
    """
    # TODO: Add assertions for robustness
    start = 0
    original_blocks = []
    network_input = network_input.to(device)
    for size in block_sizes:
        end = start + size
        abs_block = nn.Sequential(model.layers[start:end])
        original_blocks.append(abs_block)
        
        output_shape = abs_block(network_input).shape
        network_input = torch.zeros(output_shape).to(device)
        
        start = end
    return original_blocks
