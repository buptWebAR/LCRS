import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.autograd import Variable
import os
import sys
import itertools
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
tqdm.monitor_interval = 0
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix

import models as models
sys.path.append('../')
import binop
from util import binop_train
from util import bin_save_state

class RunningMean:
    def __init__(self, value=0, count=0):
        self.total_value = value
        self.count = count

    def update(self, value, count=1):
        self.total_value += value
        self.count += count

    @property
    def value(self):
        if self.count:
            return self.total_value / self.count
        else:
            return float("inf")

    def __str__(self):
        return str(self.value)

def plot_confusion_matrix(cm, classes, normalize=False,
                          title='Confusion matrix', cmap=plt.cm.Blues):
    """
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    """

    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    print(cm)

    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')

def eval_test(y_pred, y_true):
    cnf_matrix = confusion_matrix(y_true, y_pred)
    np.set_printoptions(precision=6)

    # Plot non-normalized confusion matrix
    plt.figure()
    plot_confusion_matrix(cnf_matrix, classes=target_name,
                          title='Confusion matrix, without normalization')

    # Plot normalized confusion matrix
    plt.figure()
    plot_confusion_matrix(cnf_matrix, classes=target_name, normalize=True,
                          title='Normalized confusion matrix')

    print(classification_report(y_true=y_true, y_pred=y_pred, target_names=target_name, digits=6))
    plt.show()


def save_state(model):
    print('==> Saving model ...')
    torch.save(model.state_dict(), 'models/' + args.arch + '.pth')

def train_bin(epoch):
    running_loss = RunningMean()
    running_score = RunningMean()
    model_train.train()
    pbar = tqdm(train_loader, total=len(train_loader))

    for data, target in pbar:
        batch_size = data.size(0)
        if args.cuda:
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data), Variable(target)

        optimizer.zero_grad()
        binop_train.binarization()

        output = model_train(data)
        _, preds = torch.max(output.data, dim=1)
        loss = criterion(output, target)
        running_loss.update(loss.data[0], 1)
        running_score.update(torch.sum(preds != target.data), batch_size)
        loss.backward()

        # restore weights
        binop_train.restore()
        # update
        binop_train.updateBinaryGradWeight()

        optimizer.step()
        pbar.set_description('%.6f %.6f' % (running_loss.value, running_score.value))
    print('[+] epoch %d: \nTraining: Average loss: %.6f, Average error: %.6f' % (
        epoch, running_loss.value, running_score.value))
    bin_save_state(args, model_train)

def train(epoch):
    running_loss = RunningMean()
    running_score = RunningMean()
    model_ori.train()
    pbar = tqdm(train_loader, total=len(train_loader),)
    for data, target in pbar:
        batch_size = data.size(0)
        if args.cuda:
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data), Variable(target)

        optimizer.zero_grad()
        output = model_ori(data)
        _, preds = torch.max(output.data, dim=1)
        loss = criterion(output, target)
        running_loss.update(loss.data[0], 1)
        running_score.update(torch.sum(preds != target.data), batch_size)
        loss.backward()

        optimizer.step()

        pbar.set_description('%.6f %.6f' % (running_loss.value, running_score.value))
    print('[+] epoch %d: \nTraining: Average loss: %.6f, Average error: %.6f' % (
        epoch, running_loss.value, running_score.value))
    save_state(model_ori)

def test(model, evaluate=False):
    global best_acc
    test_loss = 0
    correct = 0
    if evaluate:
        model.load_state_dict(torch.load(args.pretrained))
    else:
        model.load_state_dict(torch.load('models/' + args.arch + '.pth'))
    model.eval()
    pbar = tqdm(test_loader, total=len(test_loader))
    if evaluate:
        pred = torch.LongTensor()
        true = torch.LongTensor()
        if args.cuda:
            pred = pred.cuda()
            true = true.cuda()
    for data, target in pbar:
        if args.cuda:
            data, target = data.cuda(), target.cuda()

        data, target = Variable(data), Variable(target)
        output = model(data)
        test_loss += criterion(output, target).data[0]
        if evaluate:
            pred = torch.cat((pred, output.data.max(1, keepdim=False)[1]))
            true = torch.cat((true, target.data))
        else:
            pred = output.data.max(1, keepdim=False)[1]
            correct += pred.eq(target.data).cpu().sum()
    if evaluate:
        correct = pred.eq(true).cpu().sum()
    acc = 100. * correct / len(test_loader.dataset)
    test_loss /= len(test_loader.dataset)
    print('\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.2f}%)'.format(
        test_loss * args.batch_size, correct, len(test_loader.dataset),
        100. * correct / len(test_loader.dataset)))

    if not evaluate:
        if (acc > best_acc):
            best_acc = acc
            os.rename('models/' + args.arch + '.pth', 'models/' + args.arch + '.best.pth')
        else:
            os.remove('models/' + args.arch + '.pth')
        print('Best Accuracy: {:.2f}%\n'.format(best_acc))
    else:
        eval_test(y_pred=pred.tolist(), y_true=true.tolist())


def adjust_learning_rate(optimizer, epoch):
    """Sets the learning rate to the initial LR decayed by 10 every 15 epochs"""
    lr = args.lr * (0.1 ** (epoch // args.lr_epochs))
    print('Learning rate:', lr)
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr
    return lr


if __name__ == '__main__':
    # Training settings

    parser = argparse.ArgumentParser(description='PyTorch XNOR MNIST')

    parser.add_argument('--batch-size', type=int, default=128, metavar='N',
                        help='input batch size for training (default: 128)')
    parser.add_argument('--test-batch-size', type=int, default=128, metavar='N',
                        help='input batch size for testing (default: 128)')
    parser.add_argument('--epochs', type=int, default=15, metavar='N',
                        help='number of epochs to train (default: 100)')
    parser.add_argument('--lr-epochs', type=int, default=15, metavar='N',
                        help='number of epochs to decay the lr (default: 20)')
    parser.add_argument('--lr', type=float, default=0.01, metavar='LR',
                        help='learning rate (default: 0.01)')
    parser.add_argument('--momentum', type=float, default=0.9, metavar='M',
                        help='SGD momentum (default: 0.9)')
    parser.add_argument('--seed', type=int, default=1, metavar='S',
                        help='random seed (default: 1)')
    parser.add_argument('--log-interval', type=int, default=100, metavar='N',
                        help='how many batches to wait before logging training status')
    parser.add_argument('--arch', action='store', default='Bin_LeNet',
                        help='the MNIST network structure: Bin_LeNet')
    parser.add_argument('--pretrained', action='store', default=None,
                        help='pretrained model')
    parser.add_argument('--evaluate', action='store_true', default=False,
                        help='whether to run evaluation')
    parser.add_argument('--no_cuda', action='store_true', default=False,
                        help='disables CUDA training')
    args = parser.parse_args()
    args.cuda = not args.no_cuda and torch.cuda.is_available()
    target_name = ['0','1','2','3','4','5','6','7','8','9']
    print(args)

    if args.cuda:
        torch.cuda.manual_seed(args.seed)
    else:
        torch.manual_seed(args.seed)

    # load data
    kwargs = {'num_workers': 1, 'pin_memory': True}
    train_loader = torch.utils.data.DataLoader(
        datasets.MNIST('data', train=True, download=True,
                       transform=transforms.Compose([
                           transforms.ToTensor(),
                           transforms.Normalize((0.1307,), (0.3081,))
                       ])),
        batch_size=args.batch_size, shuffle=True, **kwargs)

    test_loader = torch.utils.data.DataLoader(
        datasets.MNIST('data', train=False, transform=transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])),
        batch_size=args.test_batch_size, shuffle=True, **kwargs)

    best_acc = 0.0
    model_ori = None
    model_train = None
    model_test = None

    # generate the model
    if args.arch == 'LeNet':
        model_ori = models.LeNet()
        if args.cuda:
            model_ori.cuda()
        if args.pretrained:
            model_ori.load_state_dict(torch.load(args.pretrained))


    elif args.arch == 'Bin_LeNet':
        model_train = models.Bin_LeNet_train()
        model_test = models.Bin_LeNet_test()
        if args.cuda:
            model_train = model_train.cuda()
            model_test = model_test.cuda()

        if args.pretrained:
            model_test.load_state_dict(torch.load(args.pretrained))
        else:
            binop_train = binop_train(model_train)

    else:
        print('ERROR: specified arch is not suppported')
        exit()

    param_dict = dict(model_train.named_parameters()) if model_ori is None else dict(model_ori.named_parameters())
    params = []

    for key, value in param_dict.items():
        if value.requires_grad:
            params += [{
                'params': [value],
                'lr': args.lr,
                'key': key
            }]
    optimizer = optim.Adam(params, lr=args.lr)
    criterion = nn.CrossEntropyLoss()


    if args.evaluate:
        if model_ori is None:
            test(model_test, evaluate=True)
        else:
            test(model_ori, evaluate=True)
        exit()

    for epoch in range(1, args.epochs + 1):
        adjust_learning_rate(optimizer, epoch)
        if model_ori is None:
            train_bin(epoch)
            test(model_test)
        else:
            train(epoch)
            test(model_ori)
