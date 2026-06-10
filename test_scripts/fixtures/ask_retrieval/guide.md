# Machine Learning Study Guide

This guide reviews four core topics for the exam. Each section is
self-contained so it can be cited independently.

## Backpropagation

Backpropagation trains a neural network by computing the gradient of the loss
with respect to every weight. It applies the chain rule layer by layer, moving
backward from the output layer to the input layer. The forward pass produces
activations; the backward pass propagates the error signal and accumulates the
partial derivatives used by gradient descent to update the weights.

## Logistic Regression and the Sigmoid Function

Logistic regression models the probability of a binary outcome. It passes a
linear combination of the inputs through the sigmoid (logistic) function, which
squashes any real number into the range zero to one. The decision boundary sits
where the sigmoid output equals one half. Training minimizes the cross-entropy
loss between the predicted probability and the true label.

## Overfitting and Regularization

Overfitting happens when a model fits the training data too closely and fails to
generalize to new data. Regularization combats this by penalizing large weights.
L2 regularization adds a squared-magnitude penalty, L1 regularization adds an
absolute-value penalty that encourages sparsity, and dropout randomly removes
units during training. The goal is to reduce variance without adding too much
bias.

## Confusion Matrix and Evaluation Metrics

A confusion matrix tabulates true positives, false positives, true negatives,
and false negatives for a classifier. Precision is the fraction of predicted
positives that are correct, recall is the fraction of actual positives that are
found, and the F1 score is their harmonic mean. Accuracy alone can be misleading
on imbalanced datasets, so precision and recall are reported together.
