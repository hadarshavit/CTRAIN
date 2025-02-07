import torch
import math
from auto_LiRPA.operators import BoundConv, BoundLinear, BoundAdd

def get_params(model):
    weights = []
    biases = []
    for p in model.named_parameters():
        if 'weight' in p[0]:
            weights.append(p)
        elif 'bias' in p[0]:
            biases.append(p)
        else:
            print('Skipping parameter {}'.format(p[0]))
    return weights, biases

def ibp_init_shi(model_ori, model):
    """
    Reinitialize the weights of the given model according to the Shi et al. (2020) initialization scheme.

    Args:
        model_ori (torch.nn.Module): The original model.
        model (auto_LiRPA.BoundedModule): The LiRPA model.

    Returns:
        None
    """
    weights, biases = get_params(model_ori)
    for i in range(len(weights)-1):
        if weights[i][1].ndim == 1:
            continue
        weight = weights[i][1]
        fan_in, fan_out = torch.nn.init._calculate_fan_in_and_fan_out(weight)
        std = math.sqrt(2 * math.pi / (fan_in**2))     
        std_before = weight.std().item()
        torch.nn.init.normal_(weight, mean=0, std=std)
        print(f'Reinitialize {weights[i][0]}, std before {std_before:.5f}, std now {weight.std():.5f}')
    for node in model._modules.values():
        if isinstance(node, BoundConv) or isinstance(node, BoundLinear):
            if len(node.inputs[0].inputs) > 0 and isinstance(node.inputs[0].inputs[0], BoundAdd):
                print(f'Adjust weights for node {node.name} due to residual connection')
                node.inputs[1].param.data /= 2