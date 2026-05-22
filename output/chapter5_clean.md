## Chapter 5 — Discrete Probability Distributions

Chapter 5 is about using probability **when the answer is a number**.

Instead of only asking:

“What is the probability of an event?”

we now ask:

“What values can X take, and what is the probability of each value?”

This chapter covers:

* Random variables
* Discrete probability distributions
* Mean / expected value
* Variance
* Standard deviation
* Binomial distribution

The chapter objectives include constructing probability distributions, finding mean/variance/expected value, and solving binomial probability problems. 

---

# 1. What this chapter is about

Imagine tossing two coins.

The outcomes are:


$$
HH,\ HT,\ TH,\ TT
$$


But in Chapter 5, we do not only care about the letters.

We define a number:


$$
X = \text{number of heads}
$$


So:

| Outcome | X = number of heads |
| ------- | ------------------: |
| TT      |                   0 |
| HT      |                   1 |
| TH      |                   1 |
| HH      |                   2 |

Now we can make a probability table:

|  X | $P(X)$ |
| -: | ---: |
|  0 |  1/4 |
|  1 |  2/4 |
|  2 |  1/4 |

This exact coin example appears in the chapter when explaining probability distributions. 

Simple idea:

**Chapter 5 turns outcomes into numbers.**

---

# 2. Variable

## Definition

A **variable** is a characteristic that can take different values.

## Plain English

It is something that can change.

## Tiny examples

| Situation            | Variable                 |
| -------------------- | ------------------------ |
| Students in class    | height                   |
| Patients in hospital | blood pressure           |
| Tossing coins        | number of heads          |
| Phone calls          | number of people on hold |

## Exam clue

If the question talks about a number that changes, like number of heads, number of calls, number of successes, number of people, it is a variable.

## Memory hint

Variable = **varies** = changes.

---

# 3. Random Variable

## Definition

A **random variable** is a variable whose value is determined by chance.

The chapter defines a random variable as a variable, usually represented by $X$, that has a numerical value determined by chance for each outcome. 

## Plain English

You do a random experiment, and the answer becomes a number.

## Tiny example

Toss two coins.

Let:


$$
X = \text{number of heads}
$$


Possible values:


$$
0,\ 1,\ 2
$$


Because the coin toss is random, $X$ is a random variable.

## Exam clue

If the question says:

“Let $X$ be the number of…”
“random variable $X$”
“find the probability distribution of $X$”

then you are working with a random variable.

## Memory hint

Random variable = **random experiment gives a number**.

---

# 4. Discrete Random Variable

## Definition

A **discrete random variable** has a finite or countable number of values.

The chapter says a discrete random variable has either a finite number of values or a countable number of values. 

## Plain English

Discrete means you can count the answers.

Usually the answers are whole numbers.

## Tiny examples

| Random variable                  | Possible values |
| -------------------------------- | --------------- |
| Number of heads in 3 coin tosses | 0, 1, 2, 3      |
| Number of children in a family   | 0, 1, 2, 3, ... |
| Number of calls received         | 0, 1, 2, 3, ... |
| Number of defective items        | 0, 1, 2, 3, ... |

## Exam clue

Use discrete when the answer is a count:

“number of people”
“number of heads”
“number of successes”
“number of calls”
“number of defective products”

## Memory hint

Discrete = **counting**.

---

# 5. Continuous Random Variable

## Definition

A **continuous random variable** has infinitely many possible values on a measurement scale.

The chapter says continuous random variables are associated with measurements on a continuous scale with no gaps. 

## Plain English

Continuous means you measure it, not count it.

It can have decimals.

## Tiny examples

| Variable    | Why continuous?            |
| ----------- | -------------------------- |
| Height      | can be 170.1 cm, 170.15 cm |
| Weight      | can be 65.3 kg             |
| Time        | can be 10.5 minutes        |
| Temperature | can be 37.2°C              |

## Exam clue

Use continuous when the question uses:

“time”
“height”
“weight”
“temperature”
“length”
“measurement”

## Memory hint

Continuous = **measurement with decimals**.

---

# 6. Discrete vs Continuous

| Point   | Discrete           | Continuous            |
| ------- | ------------------ | --------------------- |
| Type    | Counted            | Measured              |
| Values  | Separate values    | Any value in interval |
| Usually | Whole numbers      | Decimals possible     |
| Example | number of students | height of students    |
| Chapter | Chapter 5          | Chapter 6             |

## Exam trick

If you can say:

“1, 2, 3, 4…”

it is probably discrete.

If you can say:

“1.2, 1.25, 1.257…”

it is probably continuous.

---

# 7. Probability Distribution

## Definition

A **probability distribution** lists all possible values of a random variable and the probability of each value.

The chapter states that a probability distribution consists of the values a random variable can assume and the corresponding probabilities, and it can be shown by table, graph, or formula. 

## Plain English

It is a table that tells us:

“What can X be?”
and
“How likely is each value?”

## Tiny example

Toss two coins.

Let:


$$
X = \text{number of heads}
$$


|  X | $P(X)$ |
| -: | ---: |
|  0 |  1/4 |
|  1 |  2/4 |
|  2 |  1/4 |

This is a probability distribution.

## Exam clue

If the question gives a table with:


$$
X
$$


and


$$
P(X)
$$


then it is a probability distribution.

## Memory hint

Probability distribution = **value + probability table**.

---

# 8. Requirements for a Probability Distribution

For a table to be a valid probability distribution, two rules must be true.

The chapter gives these two requirements: $\sum P(x)=1$, and every $P(x)$ must be between 0 and 1. 

---

## Rule 1


$$
\sum P(X)=1
$$


All probabilities must add to 1.

## Rule 2


$$
0 \le P(X) \le 1
$$


No probability can be negative.
No probability can be greater than 1.

---

## Tiny example

|  X | $P(X)$ |
| -: | ---: |
|  0 |  0.2 |
|  1 |  0.3 |
|  2 |  0.5 |

Check:


$$
0.2+0.3+0.5=1
$$


All probabilities are between 0 and 1.

So this is valid.

---

## Invalid example

|  X | $P(X)$ |
| -: | ---: |
|  0 |  0.4 |
|  1 |  0.8 |

Check:


$$
0.4+0.8=1.2
$$


This is not valid.

---

## Exam clue

If the question asks:

“Which value completes the probability distribution?”

then add the known probabilities and subtract from 1.


$$
\text{missing probability}=1-\text{sum of known probabilities}
$$


## Memory hint

Probability table must total **one whole pizza**.

---

# 9. Mean of a Discrete Random Variable

## Definition

The mean of a discrete random variable is the long-run average value of $X$.

Formula:


$$
\mu=\sum xP(x)
$$


The chapter gives the mean formula as $\mu=\sum[x\cdot P(x)]$. 

## Plain English

Multiply each value by its probability, then add.

It tells you the average result if you repeat the experiment many times.

---

## Tiny example

|  X | $P(X)$ |
| -: | ---: |
|  0 | 0.25 |
|  1 | 0.50 |
|  2 | 0.25 |

Find mean.

### Step 1: Multiply


$$
0(0.25)=0
$$


$$
1(0.50)=0.50
$$


$$
2(0.25)=0.50
$$


### Step 2: Add


$$
\mu=0+0.50+0.50=1
$$


## Final answer


$$
\mu=1
$$


## Exam clue

If the question asks:

“mean”
“expected value”
“average value of random variable”

use:


$$
\sum xP(x)
$$


## Memory hint

Mean = **multiply then add**.

---

# 10. Expected Value

## Definition

Expected value is the same idea as the mean of a probability distribution.

Formula:


$$
E(X)=\sum xP(x)
$$


The chapter says expected value uses $E(X)=\sum X\cdot P(X)$. 

## Plain English

Expected value means:

“What do I expect on average in the long run?”

It does not always mean the exact answer you will get once.

---

## Tiny example

A game gives:

| Profit X | $P(X)$ |
| -------: | ---: |
|   10 AED |  0.5 |
|   -4 AED |  0.5 |


$$
E(X)=10(0.5)+(-4)(0.5)
$$


$$
=5-2=3
$$


Expected profit:


$$
3\text{ AED}
$$


## Exam clue

If the question uses money, profit, loss, payoff, expected gain, expected profit, use expected value.

## Memory hint

Expected value = **long-run average result**.

---

# 11. Variance of a Discrete Random Variable

## Definition

Variance measures how spread out the values of $X$ are around the mean.

Formula 1:


$$
\sigma^2=\sum (x-\mu)^2P(x)
$$


Shortcut formula:


$$
\sigma^2=\sum x^2P(x)-\mu^2
$$


The chapter gives both variance formulas, including the shortcut formula. 

## Plain English

Variance tells you how far the values are from the average.

Large variance = values are spread out.
Small variance = values are close together.

---

## Exam clue

If the question asks for variance, use:


$$
\sigma^2=\sum x^2P(x)-\mu^2
$$


This shortcut is usually faster.

## Memory hint

Variance has the square:


$$
\sigma^2
$$


So variance = **spread squared**.

---

# 12. Standard Deviation of a Discrete Random Variable

## Definition

Standard deviation is the square root of variance.

Formula:


$$
\sigma=\sqrt{\sigma^2}
$$


The chapter states that the standard deviation of a probability distribution is the square root of the variance. 

## Plain English

Standard deviation is spread, but in the original units.

## Exam clue

If the question asks for standard deviation:

1. Find variance.
2. Square root it.

## Memory hint

Standard deviation = **√variance**.

---

# 13. Example: Die Toss Mean and Standard Deviation

The chapter gives this example: find the mean and variance of the number of spots when a die is tossed. The distribution is $X=1,2,3,4,5,6$, each with probability $1/6$. 

|    X |   1 |   2 |   3 |   4 |   5 |   6 |
| ---: | --: | --: | --: | --: | --: | --: |
| $P(X)$ | 1/6 | 1/6 | 1/6 | 1/6 | 1/6 | 1/6 |

---

## A) Find the mean

### Step 1: Formula


$$
\mu=\sum xP(x)
$$


### Step 2: Substitute


$$
\mu=1\left(\frac16\right)+2\left(\frac16\right)+3\left(\frac16\right)+4\left(\frac16\right)+5\left(\frac16\right)+6\left(\frac16\right)
$$


### Step 3: Add numerator


$$
\mu=\frac{1+2+3+4+5+6}{6}
$$


$$
\mu=\frac{21}{6}
$$


### Step 4: Calculate


$$
\mu=3.5
$$


## Answer


$$
\mu=3.5
$$


### Plain meaning

If you roll a die many times, the average result will be about 3.5.

---

## B) Find the variance

### Step 1: Shortcut formula


$$
\sigma^2=\sum x^2P(x)-\mu^2
$$


### Step 2: Find $\sum x^2P(x)$


$$
1^2\left(\frac16\right)+2^2\left(\frac16\right)+3^2\left(\frac16\right)+4^2\left(\frac16\right)+5^2\left(\frac16\right)+6^2\left(\frac16\right)
$$


$$
=\frac{1+4+9+16+25+36}{6}
$$


$$
=\frac{91}{6}
$$


$$
=15.1667
$$


### Step 3: Subtract $\mu^2$


$$
\sigma^2=15.1667-(3.5)^2
$$


$$
\sigma^2=15.1667-12.25
$$


$$
\sigma^2=2.9167
$$


## Answer


$$
\sigma^2\approx2.917
$$


---

## C) Find standard deviation


$$
\sigma=\sqrt{2.917}
$$


$$
\sigma\approx1.71
$$


## Answer


$$
\sigma\approx1.71
$$


---

## Exam hint

For a probability distribution table:

1. Find $\mu=\sum xP(x)$
2. Find $\sum x^2P(x)$
3. Use $\sigma^2=\sum x^2P(x)-\mu^2$
4. Use $\sigma=\sqrt{\sigma^2}$

---

# 14. Example: People on Hold

The chapter gives this distribution for the number of people placed on hold when they call a radio talk show with four phone lines. 

|    X |    0 |    1 |    2 |    3 |    4 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| $P(X)$ | 0.18 | 0.34 | 0.23 | 0.21 | 0.04 |

Find the standard deviation.

---

## Step 1: Find the mean

Formula:


$$
\mu=\sum xP(x)
$$


Substitute:


$$
\mu=0(0.18)+1(0.34)+2(0.23)+3(0.21)+4(0.04)
$$


Calculate:


$$
\mu=0+0.34+0.46+0.63+0.16
$$


$$
\mu=1.59
$$


---

## Step 2: Find $\sum x^2P(x)$


$$
0^2(0.18)+1^2(0.34)+2^2(0.23)+3^2(0.21)+4^2(0.04)
$$


$$
=0+0.34+4(0.23)+9(0.21)+16(0.04)
$$


$$
=0+0.34+0.92+1.89+0.64
$$


$$
=3.79
$$


---

## Step 3: Find variance


$$
\sigma^2=\sum x^2P(x)-\mu^2
$$


$$
\sigma^2=3.79-(1.59)^2
$$


$$
\sigma^2=3.79-2.5281
$$


$$
\sigma^2=1.2619
$$


Approximately:


$$
\sigma^2=1.26
$$


---

## Step 4: Find standard deviation


$$
\sigma=\sqrt{1.26}
$$


$$
\sigma\approx1.12
$$


## Final answer


$$
\sigma\approx1.12
$$


---

## Exam hint

If the question asks standard deviation, do not stop at variance.

You must square root.

---

# 15. Example: Expected Profit

The chapter gives this example: a ski resort loses \$70,000 in a bad season and makes \$250,000 in a good season. The probability of a good season is 40%. Find expected profit. 

| Profit X | $P(X)$ |
| -------: | ---: |
|  250,000 | 0.40 |
|  -70,000 | 0.60 |

---

## Step 1: Identify the topic

This is expected value because it asks expected profit.

## Step 2: Formula


$$
E(X)=\sum xP(x)
$$


## Step 3: Substitute


$$
E(X)=250000(0.40)+(-70000)(0.60)
$$


## Step 4: Calculate


$$
250000(0.40)=100000
$$


$$
-70000(0.60)=-42000
$$


## Step 5: Add


$$
E(X)=100000-42000
$$


$$
E(X)=58000
$$


## Final answer


$$
\$58,000
$$


---

## Exam hint

Money + probability = expected value.

---

# 16. Binomial Distribution

## Definition

A **binomial experiment** is a probability experiment with four conditions:

1. Fixed number of trials.
2. Each trial has only two outcomes: success or failure.
3. Trials are independent.
4. Probability of success stays constant.

The chapter lists these same binomial requirements. 

---

## Plain English

Binomial means:

You repeat something a fixed number of times, and each time the answer is yes/no.

Examples:

| Situation         | Success       | Failure               |
| ----------------- | ------------- | --------------------- |
| Toss coin 5 times | head          | tail                  |
| Test 10 products  | defective     | not defective         |
| Survey 5 people   | likes product | does not like product |
| Patient test      | positive      | negative              |

---

## Exam clue

Use binomial when the question has:

“n trials”
“sample of 5”
“probability is 20%”
“success/failure”
“exactly x”
“at least one”
“at most”

---

## Memory hint

Binomial = **bi** = two outcomes.

---

# 17. Binomial Notation

| Symbol     | Meaning                |
| ---------- | ---------------------- |
| $n$        | number of trials       |
| $x$ or $r$ | number of successes    |
| $p$        | probability of success |
| $q$        | probability of failure |
| $q=1-p$    | failure probability    |

The chapter uses $p$ for probability of success, $q=1-p$ for failure, $n$ for number of trials, and $X$ for number of successes. 

---

# 18. Binomial Probability Formula

## Formula


$$
P(X=r)={}_nC_r p^r q^{n-r}
$$


or:


$$
P(X=x)=\frac{n!}{x!(n-x)!}p^xq^{n-x}
$$


## What it means

| Part      | Meaning                            |
| --------- | ---------------------------------- |
| ${}_nC_r$   | how many ways successes can happen |
| $p^r$     | probability of the successes       |
| $q^{n-r}$ | probability of the failures        |

---

## Plain English

To find exactly $r$ successes:

1. Count how many ways success positions can happen.
2. Multiply by probability of success.
3. Multiply by probability of failure.

---

# 19. Binomial Keywords

| Wording      | Meaning    |
| ------------ | ---------- |
| exactly 2    | $P(X=2)$   |
| at least 2   | $P(X\ge2)$ |
| at most 2    | $P(X\le2)$ |
| fewer than 2 | $P(X<2)$   |
| more than 2  | $P(X>2)$   |
| no successes | $P(X=0)$   |
| at least one | $1-P(X=0)$ |

---

# 20. Binomial Example: Exactly 2 Successes

Suppose:


$$
n=5,\quad p=0.20,\quad q=0.80
$$


Find probability exactly 2 people are in favor.

---

## Step 1: Identify values


$$
n=5
$$


$$
x=2
$$


$$
p=0.20
$$


$$
q=0.80
$$


---

## Step 2: Formula


$$
P(X=2)={}_5C_2(0.20)^2(0.80)^3
$$


---

## Step 3: Find combination


$$
{}_5C_2=\frac{5!}{2!3!}
$$


$$
=\frac{5\times4}{2\times1}
$$


$$
=10
$$


---

## Step 4: Substitute


$$
P(X=2)=10(0.20)^2(0.80)^3
$$


---

## Step 5: Calculate powers


$$
(0.20)^2=0.04
$$


$$
(0.80)^3=0.512
$$


---

## Step 6: Multiply


$$
P(X=2)=10(0.04)(0.512)
$$


$$
=0.2048
$$


## Final answer


$$
0.2048
$$


---

## Exam hint

“Exactly” means use the binomial formula once.

---

# 21. Binomial Example: At Least One

Suppose 20% of people like a new product. A sample of 5 people is selected. Find probability that at least one person likes it.

This is like your final exam question.

---

## Step 1: Identify values


$$
n=5
$$


$$
p=0.20
$$


$$
q=0.80
$$


---

## Step 2: Understand “at least one”

At least one means:


$$
1,2,3,4,5
$$


Instead of calculating all of these, use complement:


$$
P(X\ge1)=1-P(X=0)
$$


---

## Step 3: Find $P(X=0)$

No one likes it means all 5 do not like it.


$$
P(X=0)=(0.80)^5
$$


$$
P(X=0)=0.32768
$$


---

## Step 4: Subtract from 1


$$
P(X\ge1)=1-0.32768
$$


$$
=0.67232
$$


## Final answer


$$
0.67232
$$


---

## Exam hint

“At least one” = easiest complement question.


$$
1-P(0)
$$


---

# 22. Mean, Variance, and Standard Deviation for Binomial Distribution

For binomial distribution:

## Mean


$$
\mu=np
$$


## Variance


$$
\sigma^2=npq
$$


## Standard deviation


$$
\sigma=\sqrt{npq}
$$


The chapter objective includes finding mean, variance, and standard deviation for a binomial distribution. 

---

## Tiny example

Given:


$$
n=5,\quad p=0.20,\quad q=0.80
$$


Find mean and standard deviation.

---

### Step 1: Mean


$$
\mu=np
$$


$$
\mu=5(0.20)
$$


$$
\mu=1
$$


---

### Step 2: Variance


$$
\sigma^2=npq
$$


$$
\sigma^2=5(0.20)(0.80)
$$


$$
\sigma^2=0.80
$$


---

### Step 3: Standard deviation


$$
\sigma=\sqrt{0.80}
$$


$$
\sigma=0.894
$$


## Final answer


$$
\mu=1,\quad \sigma\approx0.89
$$


---

## Exam hint

For binomial:

Mean is not $p$.
Mean is:


$$
np
$$


---

# 23. Solving Final Exam Questions from Chapter 5

These are the final exam questions connected to Chapter 5.

---

# Question 11

**What probability value would be needed to complete the probability distribution?**

Visible probabilities:


$$
0.09,\ ?,\ 0.15,\ 0.34,\ 0.27
$$


---

## Step 1: Identify the topic

This is a probability distribution table.

For any probability distribution:


$$
\sum P(X)=1
$$


---

## Step 2: Add the known probabilities


$$
0.09+0.15+0.34+0.27
$$


$$
=0.85
$$


---

## Step 3: Find the missing value


$$
1-0.85=0.15
$$


---

## Final answer


$$
0.15
$$


Choose the option that says:

**0.15**

---

## Exam clue

Missing probability in a distribution:


$$
1-\text{sum of all other probabilities}
$$


---

## Common mistake

Adding the $X$ values instead of adding the probabilities.

Only probabilities must add to 1.

---

# Question 12

**The expected value $E(X)$ in the above table is:**

From the visible table, we use:


$$
X=-5,-3,0,1,6
$$


$$
P(X)=0.09,0.15,0.15,0.34,0.27
$$


---

## Step 1: Identify the topic

Expected value.

Use:


$$
E(X)=\sum xP(x)
$$


---

## Step 2: Multiply each $X$ by its probability

|  X | $P(X)$ |          (xP$x$) |
| -: | ---: | ---------------: |
| -5 | 0.09 | $-5(0.09)=-0.45$ |
| -3 | 0.15 | $-3(0.15)=-0.45$ |
|  0 | 0.15 |      $0(0.15)=0$ |
|  1 | 0.34 |   $1(0.34)=0.34$ |
|  6 | 0.27 |   $6(0.27)=1.62$ |

---

## Step 3: Add


$$
E(X)=-0.45-0.45+0+0.34+1.62
$$


$$
E(X)=1.06
$$


---

## Final answer


$$
E(X)=1.06
$$


If 1.06 is not in the options, choose:

**None of these answers**

---

## Exam clue

Expected value = multiply each $x$ by its probability, then add.

---

## Common mistake

Doing:


$$
\frac{-5-3+0+1+6}{5}
$$


That is not expected value because it ignores probabilities.

---

# Question 13

**The standard deviation of the random variable X in the above table is:**

Use:


$$
X=-5,-3,0,1,6
$$


$$
P(X)=0.09,0.15,0.15,0.34,0.27
$$


We already found:


$$
\mu=1.06
$$


---

## Step 1: Formula

Shortcut formula:


$$
\sigma^2=\sum x^2P(x)-\mu^2
$$


Then:


$$
\sigma=\sqrt{\sigma^2}
$$


---

## Step 2: Calculate $x^2P(x)$

|  X | $P(X)$ |       $x^2P(x)$ |
| -: | ---: | --------------: |
| -5 | 0.09 | $25(0.09)=2.25$ |
| -3 | 0.15 |  $9(0.15)=1.35$ |
|  0 | 0.15 |     $0(0.15)=0$ |
|  1 | 0.34 |  $1(0.34)=0.34$ |
|  6 | 0.27 | $36(0.27)=9.72$ |

---

## Step 3: Add


$$
\sum x^2P(x)=2.25+1.35+0+0.34+9.72
$$


$$
=13.66
$$


---

## Step 4: Variance


$$
\sigma^2=13.66-(1.06)^2
$$


$$
\sigma^2=13.66-1.1236
$$


$$
\sigma^2=12.5364
$$


---

## Step 5: Standard deviation


$$
\sigma=\sqrt{12.5364}
$$


$$
\sigma\approx3.54
$$


---

## Final answer


$$
\sigma\approx3.54
$$


If 3.54 is not in the options, choose:

**None of these answers**

---

## Exam clue

Standard deviation is always:


$$
\sqrt{\text{variance}}
$$


---

## Common mistake

Giving 12.5364 as the answer.
That is variance, not standard deviation.

---

# Question 14

**A food company launched a new product and 20% of people liked it. A sample of 5 consumers were randomly selected. Find the probability that at least one person was in favor.**

---

## Step 1: Identify the distribution

This is binomial because:

| Binomial condition     | In this question        |
| ---------------------- | ----------------------- |
| Fixed number of trials | 5 people                |
| Two outcomes           | in favor / not in favor |
| Constant probability   | 20% each person         |
| Independent trials     | randomly selected       |

---

## Step 2: Define values


$$
n=5
$$


$$
p=0.20
$$


$$
q=1-p=0.80
$$


---

## Step 3: Understand “at least one”

“At least one” means:


$$
1,2,3,4,5
$$


Use complement:


$$
P(X\ge1)=1-P(X=0)
$$


---

## Step 4: Find $P(X=0)$

No one is in favor means all 5 are not in favor.


$$
P(X=0)=(0.80)^5
$$


$$
P(X=0)=0.32768
$$


---

## Step 5: Subtract from 1


$$
P(X\ge1)=1-0.32768
$$


$$
P(X\ge1)=0.67232
$$


---

## Final answer


$$
0.67232
$$


So the answer is:

**B) 0.67232**

---

## Exam clue

“At least one” = $1-P(0)$

---

## Common mistake

Calculating exactly one:


$$
{}_5C_1(0.20)^1(0.80)^4
$$


That gives only one person in favor, not at least one.

---

# Question 15

**Same food company question: find the mean and standard deviation for the number of people who were in favor.**

Given:


$$
n=5
$$


$$
p=0.20
$$


$$
q=0.80
$$


---

## Step 1: Mean formula


$$
\mu=np
$$


---

## Step 2: Substitute


$$
\mu=5(0.20)
$$


$$
\mu=1
$$


---

## Step 3: Standard deviation formula


$$
\sigma=\sqrt{npq}
$$


---

## Step 4: Substitute


$$
\sigma=\sqrt{5(0.20)(0.80)}
$$


---

## Step 5: Calculate inside the square root


$$
5(0.20)(0.80)=0.80
$$


---

## Step 6: Square root


$$
\sigma=\sqrt{0.80}
$$


$$
\sigma\approx0.89
$$


---

## Final answer


$$
\mu=1,\quad \sigma\approx0.89
$$


Choose the option that says:


$$
\mu=1,\ \sigma=0.89
$$


---

## Exam clue

For binomial mean and standard deviation:


$$
\mu=np
$$


$$
\sigma=\sqrt{npq}
$$


---

## Common mistake

Using:


$$
\sigma=npq
$$


That is variance, not standard deviation.

---

# Chapter 5 Mini Cheat Sheet

| Topic                           | Formula / Rule                |
| ------------------------------- | ----------------------------- |
| Probability distribution rule 1 | $\sum P(X)=1$                 |
| Probability distribution rule 2 | $0\le P(X)\le1$               |
| Mean / expected value           | $\mu=E(X)=\sum xP(x)$         |
| Variance                        | $\sigma^2=\sum (x-\mu)^2P(x)$ |
| Shortcut variance               | $\sigma^2=\sum x^2P(x)-\mu^2$ |
| Standard deviation              | $\sigma=\sqrt{\sigma^2}$      |
| Binomial failure probability    | $q=1-p$                       |
| Binomial probability            | $P(X=r)={}_nC_rp^rq^{n-r}$     |
| Binomial mean                   | $\mu=np$                      |
| Binomial variance               | $\sigma^2=npq$                |
| Binomial standard deviation     | $\sigma=\sqrt{npq}$           |

---

# When You See This Wording, Use This Method

| Wording in exam                  | Use this                        |
| -------------------------------- | ------------------------------- |
| “random variable X”              | List possible values of X       |
| “probability distribution”       | Check $P(X)$ values and total   |
| “complete the distribution”      | $1-$ sum of known probabilities |
| “expected value”                 | $\sum xP(x)$                    |
| “mean of random variable”        | $\sum xP(x)$                    |
| “variance”                       | $\sum x^2P(x)-\mu^2$            |
| “standard deviation”             | square root of variance         |
| “two outcomes”                   | binomial may be used            |
| “fixed number of trials”         | binomial clue                   |
| “exactly x successes”            | binomial formula                |
| “at least one”                   | $1-P(0)$                        |
| “mean of binomial”               | $np$                            |
| “standard deviation of binomial” | $\sqrt{npq}$                    |

---

# Most Likely Chapter 5 Exam Question Types

1. Identify discrete vs continuous random variables.
2. Complete a probability distribution table.
3. Check whether a probability distribution is valid.
4. Find expected value / mean.
5. Find variance.
6. Find standard deviation.
7. Recognize a binomial experiment.
8. Solve exactly $x$ successes using binomial formula.
9. Solve “at least one” using complement.
10. Find binomial mean and standard deviation.

---

# Quick Practice With Answers

## Practice 1

A probability distribution has probabilities:


$$
0.20,\ 0.30,\ ?,\ 0.10
$$


Find the missing probability.

### Solution


$$
0.20+0.30+0.10=0.60
$$


$$
1-0.60=0.40
$$


Answer:


$$
0.40
$$


---

## Practice 2

|    X |   0 |   1 |   2 |
| ---: | --: | --: | --: |
| $P(X)$ | 0.2 | 0.5 | 0.3 |

Find expected value.

### Solution


$$
E(X)=0(0.2)+1(0.5)+2(0.3)
$$


$$
=0+0.5+0.6
$$


$$
=1.1
$$


Answer:


$$
1.1
$$


---

## Practice 3

Using the same table, find $\sum x^2P(x)$.

### Solution


$$
0^2(0.2)+1^2(0.5)+2^2(0.3)
$$


$$
=0+0.5+4(0.3)
$$


$$
=0+0.5+1.2
$$


$$
=1.7
$$


Answer:


$$
1.7
$$


---

## Practice 4

Using the same table, find variance.

We know:


$$
\mu=1.1
$$


$$
\sum x^2P(x)=1.7
$$


### Solution


$$
\sigma^2=1.7-(1.1)^2
$$


$$
=1.7-1.21
$$


$$
=0.49
$$


Answer:


$$
0.49
$$


---

## Practice 5

Using the same table, find standard deviation.

### Solution


$$
\sigma=\sqrt{0.49}
$$


$$
=0.7
$$


Answer:


$$
0.7
$$


---

## Practice 6

A quiz has 4 true/false questions. Probability of guessing correctly is 0.5. Find probability of exactly 3 correct.

### Step 1: Values


$$
n=4,\quad x=3,\quad p=0.5,\quad q=0.5
$$


### Step 2: Formula


$$
P(X=3)={}_4C_3(0.5)^3(0.5)^1
$$


### Step 3: Combination


$$
{}_4C_3=4
$$


### Step 4: Calculate


$$
P(X=3)=4(0.125)(0.5)
$$


$$
=4(0.0625)
$$


$$
=0.25
$$


Answer:


$$
0.25
$$


---

## Practice 7

A sample of 6 people is selected. Probability a person likes the product is 0.30. Find probability at least one likes it.

### Step 1: Values


$$
n=6,\quad p=0.30,\quad q=0.70
$$


### Step 2: Complement


$$
P(X\ge1)=1-P(X=0)
$$


$$
=1-(0.70)^6
$$


$$
=1-0.117649
$$


$$
=0.882351
$$


Answer:


$$
0.8824
$$


---

# Final Chapter 5 Memory Box

Memorize these:


$$
\mu=E(X)=\sum xP(x)
$$


$$
\sigma^2=\sum x^2P(x)-\mu^2
$$


$$
\sigma=\sqrt{\sigma^2}
$$


For binomial:


$$
q=1-p
$$


$$
P(X=r)={}_nC_rp^rq^{n-r}
$$


$$
\mu=np
$$


$$
\sigma=\sqrt{npq}
$$


And the biggest exam shortcut:

**“At least one” = $1-P(0)$**.
