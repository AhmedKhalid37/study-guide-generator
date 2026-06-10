# Neural Network Basics (source notes)

These are raw lecture notes used as the *source* input for the sample golden
spec. They are intentionally small and deterministic.

## Page 1

A neural network is built from layers of units. Each unit applies an activation
function to a weighted sum of its inputs. Training adjusts the weights using
gradient descent, and the gradients are computed by backpropagation through the
network.

## Page 2

Key facts:

- The logistic (sigmoid) activation maps any real number to (0, 1).
- For an input z = 1.43, the logistic output is exp(1.43) / (1 + exp(1.43)).
- Softmax outputs are non-negative and sum to 1.
- A small worked sum: 2 + 3 = 5.
