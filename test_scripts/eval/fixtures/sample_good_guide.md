# Neural Network Study Guide

## Overview

This guide reviews how a feed-forward neural network learns. It covers the role
of the activation function, how errors flow backward through backpropagation, and
how gradient descent updates the weights (p. 1).

## Key Concepts

- **Activation function** — a non-linearity applied to each unit's weighted sum.
  The logistic (sigmoid) activation maps any real value into the open interval
  (0, 1) (pp. 1-2).
- **Backpropagation** — the algorithm that computes the gradient of the loss with
  respect to every weight by applying the chain rule layer by layer (p. 1).
- **Gradient descent** — the optimization step that nudges each weight in the
  direction that reduces the loss (p. 1).

| Concept | Role |
| --- | --- |
| Activation function | Adds non-linearity |
| Backpropagation | Computes gradients |
| Gradient descent | Updates weights |

## Worked Examples

A small arithmetic check from the source example (p. 2):

2 + 3 = 5

Logistic output for z = 1.43:

Source page for the logistic example: (p. 2).

exp(1.43) / (1 + exp(1.43)) ≈ 0.806

The square root example: sqrt(16) = 4.

## Practice Questions

1. What does an activation function add to a network?
2. Which algorithm computes the gradients used by gradient descent?
3. Compute the logistic output for z = 0 (answer: 0.5).
