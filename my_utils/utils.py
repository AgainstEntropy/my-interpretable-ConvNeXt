# -*- coding: utf-8 -*-
# @Date    : 2021/12/18 19:39
# @Author  : WangYihao
# @File    : functions.py


import torch
from torch import nn

import time


def Conv_BN_Relu(in_channel, out_channel, kernel_size=(3, 3), stride=None):
    if stride is not None:
        conv_layer = nn.Conv2d(in_channel, out_channel, kernel_size, stride, bias=False)
    else:
        conv_layer = nn.Conv2d(in_channel, out_channel, kernel_size, padding='same', bias=False)
    return nn.Sequential(
        conv_layer,
        nn.BatchNorm2d(out_channel),
        nn.ReLU()
    )


def sim(imgs_act, img):
    """

    Args:
        imgs_act ():
        img ():

    Returns: Similarity scores between activations and original image.

    """
    assert len(imgs_act.size()) >= 3
    chans = imgs_act.size(0)
    if len(img.size() >= 3):
        img = img.squeeze()
    sims = torch.zeros(chans)
    for chan, act in enumerate(imgs_act):
        sims[chan] = (act * img).sum() / \
                  torch.sqrt(torch.sum(act ** 2) * torch.sum(img ** 2))
    return torch.softmax(sims, dim=0)


def save_model(model, optimizer, model_type, dataset="unfilled", acc=00):
    model_paras = model.state_dict()
    print("Model parameters:")
    for k, v in model_paras.items():
        print(f"{k}:\t {v.size()}")

    optim_paras = optimizer.state_dict()
    print("\nOptimizer parameters:")
    for k, v in optim_paras.items():
        print(f"{k}")

    save_time = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = f"saved_models/{acc}_{dataset}_{model_type}_{save_time}.pt"
    torch.save({
        "model_paras": model_paras,
        "optim_paras": optim_paras
    }, save_path)
    print(f"\nSuccessfully saved to {save_path}")


def get_device(model):
    return next(model.parameters()).device


def check_accuracy(test_model, loader, training=False):
    num_correct = 0
    num_samples = 0
    device = get_device(test_model)
    test_model.eval()  # set model to evaluation mode
    tic = time.time()
    with torch.no_grad():
        for batch_idx, (X, Y) in enumerate(loader):
            X = X.to(device, dtype=torch.float32)  # move to device, e.g. GPU
            Y = Y.to(device, dtype=torch.int)
            scores = test_model(X)
            num_correct += (scores.argmax(axis=1) == Y).sum()
            num_samples += len(scores)
    test_acc = float(num_correct) / num_samples
    if training:
        return test_acc
    else:
        print(f"Test accuracy is : {100. * test_acc:.2f}%\tInfer time: {time.time() - tic}")


def train(model, optimizer, scheduler, loss_fn, train_loader,
          check_fn, check_loaders, batch_step, epochs=2, log_every=10, writer=None):
    """

    Args:
        batch_step (int):
        epochs (int):
        log_every (int): log info per log_every batches.
        writer :

    Returns:
        batch_step (int):
    """
    device = get_device(model)
    # batch_size = train_loader.batch_size
    check_loader_train = check_loaders['train']
    check_loader_val = check_loaders['val']
    iters = len(train_loader)
    for epoch in range(1, epochs + 1):
        tic = time.time()
        for batch_idx, (X, Y) in enumerate(train_loader):
            batch_step += 1
            model.train()
            X = X.to(device, dtype=torch.float32)
            Y = Y.to(device, dtype=torch.int64)
            # print(X.device, model.device)
            scores = model(X)
            loss = loss_fn(scores, Y)
            if writer is not None:
                writer.add_scalar('Metric/loss', loss.item(), batch_step)
                writer.add_scalar('Hpara/lr', optimizer.param_groups[0]['lr'], batch_step)

            # back propagate
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step(batch_step / iters)

            # check accuracy
            if batch_idx % log_every == 0:
                model.eval()
                train_acc = check_fn(model, check_loader_train, training=True)
                val_acc = check_fn(model, check_loader_val, training=True)
                if writer is not None:
                    writer.add_scalars('Metric/acc', {'train': train_acc, 'val': val_acc}, batch_step)
                print(f'Epoch: {epoch} [{batch_idx}/{iters}]\tLoss: {loss:.4f}\t'
                      f'Val acc: {100. * val_acc:.1f}%')

        print(f'====> Epoch: {epoch}\tTime: {time.time() - tic}s')

    return batch_step
