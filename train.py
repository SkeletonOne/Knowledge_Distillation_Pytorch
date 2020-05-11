# import the required models
import torch
import torch.nn as nn
import torch.functional
import torchvision
import torchvision.transforms as transforms
import torch.optim as optim
# from torch.autograd import Variable

from customs import Functions, Metrics, progress_bar
from tqdm import tqdm
import numpy as np
import time
import os
import copy
# from models.resnet import ResNet18
from models.googlenet import GoogLeNet

def train(model, optimizer, loss_fn, dataloader):
    """Train the model on `num_steps` batches
    Args:
        model: (torch.nn.Module) the neural network
        optimizer: (torch.optim) optimizer for parameters of model
        lr_scheduler: (torch.optim.lr_scheduler) Adjustment function for the learning rate
        loss_fn: a function that takes batch_output and batch_labels and computes the loss for the batch
        dataloader: (DataLoader) a torch.utils.data.DataLoader object that fetches training data
        num_steps: (int) number of batches to train on, each of size params.batch_size
    """

    # Set the model into train mode
    model.train()

    train_loss = 0
    correct = 0
    total = 0

    for batch_idx, (train_batch, labels_batch) in enumerate(dataloader):

        # move the data onto the device
        train_batch, labels_batch = train_batch.to(device), labels_batch.to(device)

        # # convert to torch Variables
        # train_batch, labels_batch = Variable(train_batch), Variable(labels_batch)

        # clear the previous grad 
        optimizer.zero_grad()

        # compute model outputs and loss
        outputs = model(train_batch)
        loss = loss_fn(outputs, labels_batch)
        loss.backward()

        # after computing gradients based on current batch loss,
        # apply them to parameters
        optimizer.step()

        train_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels_batch.size(0)
        correct += predicted.eq(labels_batch).sum().item()

        progress_bar(batch_idx, len(dataloader), 'Train Loss: %.3f | Train Acc: %.3f%% (%d/%d)'
                     % (train_loss/(batch_idx+1), 100.*correct/total, correct, total))


def eval(model, optimizer, loss_fn, dataloader):
    """Train the model on `num_steps` batches
    Args:
        model: (torch.nn.Module) the neural network
        optimizer: (torch.optim) optimizer for parameters of model
        loss_fn: a function that takes batch_output and batch_labels and computes the loss for the batch
        dataloader: (DataLoader) a torch.utils.data.DataLoader object that fetches training datas
        num_steps: (int) number of batches to train on, each of size params.batch_size
    """

    # Set the model into test mode
    model.eval()

    test_loss = 0
    correct = 0
    total = 0

    # check global variable `best_accuracy`
    global best_accuracy

    with torch.no_grad():
        for batch_idx, (test_batch, labels_batch) in enumerate(dataloader):

            # move the data onto device
            test_batch, labels_batch = test_batch.to(device), labels_batch.to(device)

            # compute the model output
            outputs = model(test_batch)
            loss = loss_fn(outputs, labels_batch)
            
            test_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels_batch.size(0)
            correct += predicted.eq(labels_batch).sum().item()

            progress_bar(batch_idx, len(dataloader), 'Test Loss: %.3f | Test Acc: %.3f%% (%d/%d)'
                         % (test_loss/(batch_idx+1), 100.*correct/total, correct, total))

    # save checkpoint
    acc = 100. * correct/total
    if acc > best_accuracy:
        print("Saving the model.....")
        save_path = "/home/htut/Desktop/Knowledge_Distillation_Pytorch/checkpoints/teachers/googlenet/googlenet_acc:{}.pt".format(acc)
        torch.save(model.state_dict(), save_path)
        
        best_accuracy = acc


def train_and_evaluate(model, train_dataloader, test_dataloader, optimizer, loss_fn, total_epochs):
    """Train the model and evaluate every epoch.
    Args:
        model: (torch.nn.Module) the neural network
        train_dataloader: (DataLoader) a torch.utils.data.DataLoader object that fetches training data
        val_dataloader: (DataLoader) a torch.utils.data.DataLoader object that fetches validation data
        optimizer: (torch.optim) optimizer for parameters of model
        lr_scheduler: (torch.optim.lr_scheduler) Adjustment function for the learning rate
        loss_ft: a function that takes batch_output and batch_labels and computes the loss for the batch
        total_epochs: total number of epochs
    """

    for epoch in range(total_epochs):

        # Run one epoch for both train and test
        print("Epoch {}/{}".format(epoch + 1, total_epochs))

        if epoch == 150:
            optimizer = optim.SGD(model.parameters(), lr=0.01,
                      momentum=0.9, weight_decay=5e-4)
        elif epoch == 250:
            optimizer = optim.SGD(model.parameters(), lr=0.001,
                      momentum=0.9, weight_decay=5e-4)

        # compute number of batches in one epoch(one full pass over the training set)
        train(model, optimizer, loss_fn, train_dataloader)

        # Evaluate for one epoch on test set
        eval(model, optimizer, loss_fn, test_dataloader)
        

if __name__ == "__main__":
    

    F = Functions()
    M = Metrics()

    transform_train = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
    ])

    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
    ])

    # The dataset that we are going to train the network is : CIFAR-10 dataset

    trainset = torchvision.datasets.CIFAR10(root='/home/htut/Desktop/Knowledge_Distillation_Pytorch/datasets', train=True,
                                            download=True, transform=transform_train)
    trainloader = torch.utils.data.DataLoader(trainset, batch_size=128,
                                            shuffle=True, num_workers=4)

    testset = torchvision.datasets.CIFAR10(root="/home/htut/Desktop/Knowledge_Distillation_Pytorch/datasets", train=False,
                                            download=True, transform=transform_test)
    testloader = torch.utils.data.DataLoader(testset, batch_size=100,
                                            shuffle=False, num_workers=4)

    classes = ('plane', 'car', 'bird', 'cat', 'deeer',
                'dog', 'frog', 'horse', 'ship', 'truck')

    # setup device for training
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # Setup best accuracy for comparing and model checkpoints
    best_accuracy = 0.0

    # Configure the Network

    """
    Finetuning code snippet : need to change the output dimensions of resnet
    # path of the pretrained weights of resnet-18
    weights_path = "/home/htut/Desktop/Knowledge_Distillation_Pytorch/models/resnet/resnet18-5c106cde.pth"
    model_fn = ResNet18()
    model_fn.load_state_dict(torch.load(weights_path))
    print("Weights have been loaded!")
    num_ftrs = model_fn.fc.in_features

    # Set the output dimensions into 10 (total number of classes in cifar-10 dataaset)
    model_fn.fc = nn.Linear(num_ftrs, 10)
    """
    # You can swap out any kind of architectire from /models in here
    # model_fn = ResNet18()
    model_fn = GoogLeNet()
    model_fn = model_fn.to(device)

    # Setup the loss function
    criterion = nn.CrossEntropyLoss()

    # Setup the optimizer method for all the parameters
    optimizer_fn = optim.SGD(model_fn.parameters(), lr=0.1, weight_decay=5e-4)

    train_and_evaluate(model=model_fn, train_dataloader=trainloader, test_dataloader=testloader,
                        optimizer=optimizer_fn, loss_fn=criterion, total_epochs=350)

    