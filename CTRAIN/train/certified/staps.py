from concurrent.futures import ProcessPoolExecutor
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from auto_LiRPA import BoundedModule, PerturbationLpNorm

from CTRAIN.bound.taps import GradExpander
from CTRAIN.eval import eval_acc, eval_certified, eval_epoch
from CTRAIN.bound import bound_ibp
from CTRAIN.train.certified.eps_scheduler import SmoothedScheduler
from CTRAIN.train.certified.losses import get_ibp_loss, get_sabr_loss, get_taps_loss
from CTRAIN.train.certified.initialisation import ibp_init_shi
from CTRAIN.train.certified.regularisers import get_shi_regulariser
from CTRAIN.util import save_checkpoint
from CTRAIN.train.certified.regularisers import get_l1_reg
from CTRAIN.train.certified.util import split_network


def staps_train_model(
    original_model,
    hardened_model,
    train_loader,
    val_loader=None,
    start_epoch=0,
    end_epoch=None,
    num_epochs=None,
    eps=0.3,
    eps_std=0.3,
    eps_schedule=(0, 20, 50),
    eps_schedule_unit="epoch",
    eps_scheduler_args=dict(),
    optimizer=None,
    subselection_ratio=0.4,
    lr_decay_schedule=(15, 25),
    lr_decay_factor=10,
    lr_decay_schedule_unit="epoch",
    n_classes=10,
    gradient_clip=None,
    l1_regularisation_weight=0.00001,
    shi_regularisation_weight=0.5,
    shi_reg_decay=True,
    gradient_expansion_alpha=5.0,
    sabr_pgd_steps=8,
    sabr_pgd_step_size=0.5,
    sabr_pgd_restarts=1,
    sabr_pgd_early_stopping=True,
    sabr_pgd_decay_factor=0.1,
    sabr_pgd_decay_checkpoints=(4, 7),
    taps_pgd_steps=20,
    taps_pgd_step_size=None,
    taps_pgd_restarts=1,
    taps_pgd_decay_factor=0.2,
    taps_pgd_decay_checkpoints=(5, 7),
    taps_gradient_link_thresh=0.5,
    taps_gradient_link_tolerance=0.00001,
    results_path="./results",
    device="cuda",
):
    """
    Trains a hardened model using the STAPS training method.

    Args:
        original_model (torch.nn.Module): The original model to be hardened.
        hardened_model (auto_LiRPA.BoundedModule): The bounded model to be trained.
        train_loader (torch.utils.data.DataLoader): DataLoader for the training data.
        val_loader (torch.utils.data.DataLoader, optional): DataLoader for the validation data. Defaults to None.
        start_epoch (int, optional): Epoch to start training from. Defaults to 0.
        end_epoch (int, optional): Epoch to prematurely end training at. Defaults to None.
        num_epochs (int, optional): Number of epochs to train the model. Defaults to None.
        eps (float, optional): Epsilon value for perturbation. Defaults to 0.3.
        eps_std (float, optional): Standardised epsilon value. Defaults to 0.3.
        eps_schedule (tuple, optional): Schedule for epsilon values. Defaults to (0, 20, 50).
        eps_schedule_unit (str, optional): Unit for epsilon schedule ('epoch' or 'batch'). Defaults to 'epoch'.
        eps_scheduler_args (dict, optional): Additional arguments for the epsilon scheduler. Defaults to dict().
        optimizer (torch.optim.Optimizer, optional): Optimizer for training. Defaults to None.
        subselection_ratio (float, optional): Ratio for subselection in SABR loss. Defaults to 0.4.
        lr_decay_schedule (tuple, optional): Schedule for learning rate decay. Defaults to (15, 25).
        lr_decay_factor (float, optional): Factor by which to decay the learning rate. Defaults to 10.
        lr_decay_schedule_unit (str, optional): Unit for learning rate decay schedule ('epoch' or 'batch'). Defaults to 'epoch'.
        n_classes (int, optional): Number of classes in the dataset. Defaults to 10.
        gradient_clip (float, optional): Value for gradient clipping. Defaults to None.
        l1_regularisation_weight (float, optional): Weight for L1 regularization. Defaults to 0.00001.
        shi_regularisation_weight (float, optional): Weight for SHI regularization. Defaults to 0.5.
        shi_reg_decay (bool, optional): Whether to decay SHI regularization. Defaults to True.
        gradient_expansion_alpha (float, optional): Alpha value for gradient expansion. Defaults to 5.
        sabr_pgd_steps (int, optional): Number of PGD steps for SABR loss. Defaults to 8.
        sabr_pgd_step_size (float, optional): Step size for PGD in SABR loss. Defaults to 0.5.
        sabr_pgd_restarts (int, optional): Number of PGD restarts for SABR loss. Defaults to 1.
        sabr_pgd_early_stopping (bool, optional): Whether to use early stopping in PGD for SABR loss. Defaults to True.
        sabr_pgd_decay_factor (float, optional): Decay factor for PGD in SABR loss. Defaults to 0.1.
        sabr_pgd_decay_checkpoints (tuple, optional): Checkpoints for PGD decay in SABR loss. Defaults to (4, 7).
        taps_pgd_steps (int, optional): Number of PGD steps for TAPS loss. Defaults to 20.
        taps_pgd_step_size (float, optional): Step size for PGD in TAPS loss. Defaults to None.
        taps_pgd_restarts (int, optional): Number of PGD restarts for TAPS loss. Defaults to 1.
        taps_pgd_decay_factor (float, optional): Decay factor for PGD in TAPS loss. Defaults to 0.2.
        taps_pgd_decay_checkpoints (tuple, optional): Checkpoints for PGD decay in TAPS loss. Defaults to (5, 7).
        taps_gradient_link_thresh (float, optional): Threshold for gradient linking in TAPS loss. Defaults to 0.5.
        taps_gradient_link_tolerance (float, optional): Tolerance for gradient linking in TAPS loss. Defaults to 0.00001.
        start_epoch (int, optional): Epoch to start training from. Defaults to 0.
        results_path (str, optional): Path to save training results. Defaults to "./results".
        device (str, optional): Device to use for training ('cuda' or 'cpu'). Defaults to 'cuda'.

    Returns:
        (autoLiRPA.BoundedModule): The trained bounded model.
    """
    if end_epoch is None:
        end_epoch = num_epochs

    criterion = nn.CrossEntropyLoss(reduction="none")
    if start_epoch == 0:
        ibp_init_shi(original_model, hardened_model)

    no_batches = 0
    cur_lr = optimizer.param_groups[-1]["lr"]

    eps_scheduler = SmoothedScheduler(
        num_epochs=num_epochs,
        eps=eps,
        mean=train_loader.mean,
        std=train_loader.std,
        eps_schedule_unit=eps_schedule_unit,
        eps_schedule=eps_schedule,
        batches_per_epoch=len(train_loader),
        start_epoch=start_epoch,
        **eps_scheduler_args,
    )

    cur_eps = eps_scheduler.get_cur_eps()

    for epoch in range(start_epoch, end_epoch):

        if start_epoch > epoch:
            continue

        epoch_nat_err = 0
        epoch_rob_err = 0

        if lr_decay_schedule_unit == "epoch":
            if epoch + 1 in lr_decay_schedule:
                print("LEARNING RATE DECAYED!")
                cur_lr = cur_lr * lr_decay_factor
                for g in optimizer.param_groups:
                    g["lr"] = cur_lr

        print(
            f"[{epoch + 1}/{num_epochs}]: eps {[channel_eps for channel_eps in cur_eps]}"
        )

        for block in hardened_model.bounded_blocks:
            block.train()

        running_loss = 0.0

        for batch_idx, (data, target) in enumerate(train_loader):

            if start_epoch > epoch:
                eps_scheduler.batch_step()
                continue

            cur_eps = eps_scheduler.get_cur_eps().reshape(-1, 1, 1)

            ptb = PerturbationLpNorm(
                eps=cur_eps,
                norm=np.inf,
                x_L=torch.clamp(data - cur_eps, train_loader.min, train_loader.max).to(
                    device
                ),
                x_U=torch.clamp(data + cur_eps, train_loader.min, train_loader.max).to(
                    device
                ),
            )

            if lr_decay_schedule_unit == "batch":
                if no_batches + 1 in lr_decay_schedule:
                    print("LEARNING RATE DECAYED!")
                    cur_lr = cur_lr * lr_decay_factor
                    for g in optimizer.param_groups:
                        g["lr"] = cur_lr

            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            clean_output = hardened_model(data)
            regular_err = torch.sum(
                torch.argmax(clean_output, dim=1) != target
            ).item() / data.size(0)
            epoch_nat_err += regular_err
            clean_loss = criterion(clean_output, target).mean()

            if eps_scheduler.get_cur_eps(normalise=False) == 0.0:
                loss = clean_loss
            elif eps_scheduler.get_cur_eps(normalise=False) != 0.0 and (
                eps_scheduler.get_cur_eps(normalise=False)
                != eps_scheduler.get_max_eps(normalise=False)
            ):
                reg_loss, robust_err, adv_err = get_sabr_loss(
                    hardened_model=hardened_model,
                    original_model=original_model,
                    data_max=train_loader.max.to(device),
                    data_min=train_loader.min.to(device),
                    data=data,
                    target=target,
                    eps=torch.tensor(cur_eps, device=device),
                    subselection_ratio=subselection_ratio,
                    criterion=criterion,
                    device=device,
                    n_classes=n_classes,
                    pgd_steps=sabr_pgd_steps,
                    pgd_step_size=sabr_pgd_step_size,
                    pgd_restarts=sabr_pgd_restarts,
                    pgd_early_stopping=sabr_pgd_early_stopping,
                    pgd_decay_checkpoints=sabr_pgd_decay_checkpoints,
                    pgd_decay_factor=sabr_pgd_decay_factor,
                    return_stats=True,
                )

                loss_regularisers = get_shi_regulariser(
                    model=hardened_model,
                    ptb=ptb,
                    data=data,
                    target=target,
                    eps_scheduler=eps_scheduler,
                    n_classes=n_classes,
                    device=device,
                    included_regularisers=["relu", "tightness"],
                    verbose=False,
                    regularisation_decay=shi_reg_decay,
                )
                epoch_rob_err += robust_err
                loss_regularisers = shi_regularisation_weight * loss_regularisers
                loss = reg_loss + loss_regularisers

            elif eps_scheduler.get_cur_eps(
                normalise=False
            ) == eps_scheduler.get_max_eps(normalise=False):
                sabr_args = dict(
                    hardened_model=hardened_model,
                    original_model=original_model,
                    data_max=train_loader.max.to(device),
                    data_min=train_loader.min.to(device),
                    data=data,
                    target=target,
                    eps=torch.tensor(cur_eps, device=device),
                    subselection_ratio=subselection_ratio,
                    device=device,
                    n_classes=n_classes,
                    n_steps=sabr_pgd_steps,
                    step_size=sabr_pgd_step_size,
                    restarts=sabr_pgd_restarts,
                    early_stopping=sabr_pgd_early_stopping,
                    decay_checkpoints=sabr_pgd_decay_checkpoints,
                    decay_factor=sabr_pgd_decay_factor,
                )
                loss, robust_err = get_taps_loss(
                    original_model=original_model,
                    hardened_model=hardened_model,
                    bounded_blocks=hardened_model.bounded_blocks,
                    criterion=criterion,
                    data=data,
                    target=target,
                    n_classes=n_classes,
                    ptb=ptb,
                    device=device,
                    pgd_steps=taps_pgd_steps,
                    pgd_restarts=taps_pgd_restarts,
                    pgd_step_size=taps_pgd_step_size,
                    pgd_decay_checkpoints=taps_pgd_decay_checkpoints,
                    pgd_decay_factor=taps_pgd_decay_factor,
                    gradient_link_thresh=taps_gradient_link_thresh,
                    gradient_link_tolerance=taps_gradient_link_tolerance,
                    propagation="SABR",
                    sabr_args=sabr_args,
                    return_stats=True,
                )

                epoch_rob_err += robust_err

            if l1_regularisation_weight is not None:
                l1_regularisation = l1_regularisation_weight * get_l1_reg(
                    model=original_model, device=device
                )
                loss += l1_regularisation

            loss.backward()

            if gradient_clip is not None:
                nn.utils.clip_grad_value_(
                    hardened_model.parameters(), clip_value=gradient_clip
                )

            optimizer.step()

            running_loss += loss.item()
            eps_scheduler.batch_step()
            no_batches += 1

        train_acc_nat = 1 - epoch_nat_err / len(train_loader)
        train_acc_cert = 1 - epoch_rob_err / len(train_loader)

        print(
            f"Epoch [{epoch+1}/{num_epochs}], Train Loss: {running_loss/len(train_loader):.4f}"
        )
        print(f"\t Natural Acc. Train: {train_acc_nat:.4f}")
        print(f"\t Adv. Acc. Train: N/A")
        print(f"\t Certified Acc. Train: {train_acc_cert:.4f}")

        if results_path is not None:
            save_checkpoint(
                hardened_model, optimizer, running_loss, epoch + 1, results_path
            )

    return hardened_model
