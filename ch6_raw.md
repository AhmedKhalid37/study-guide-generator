## Chapter 6 — Continuous Probability Distributions / Normal Distribution

Chapter 6 is about probabilities for **measurements**.

In Chapter 5, we studied **discrete** random variables, like:

* number of heads
* number of people
* number of successes

In Chapter 6, we study **continuous** random variables, like:

* time
* height
* weight
* temperature
* scores

This chapter mainly focuses on the **normal distribution**, **z-score**, and using the **standard normal table**. The chapter outline includes normal distribution and applications of the normal distribution. 

---

# 1. What this chapter is about

Chapter 6 helps you answer questions like:

“What is the probability that a value is less than 900?”
“What is the probability that a value is between 1100 and 1225?”
“What is the probability that a value exceeds 1500?”
“How far is a score from the mean?”

The main tool is:

$$z=\frac{x-\mu}{\sigma}$$

This changes a normal value $x$ into a **z-score**.

---

# 2. Continuous Random Variable

## Definition

A **continuous random variable** is a variable that can take infinitely many values.

## Plain English

It is usually something you **measure**, not count.

It can have decimals.

## Tiny examples

| Variable    | Example value |
| ----------- | ------------: |
| Time        |  10.5 minutes |
| Height      |      172.3 cm |
| Weight      |      68.75 kg |
| Temperature |        37.2°C |
| Exam score  |          84.5 |

## How to recognize it in exam questions

Look for words like:

“time”
“weight”
“height”
“length”
“temperature”
“score”
“measurement”

## Memory hint

Continuous = **can continue forever between values**.

Example:

Between 1 and 2, you can have:

$$1.1,\ 1.11,\ 1.111,\ 1.1111$$

and so on.

---

# 3. Normal Distribution

## Definition

A **normal distribution** is a continuous probability distribution shaped like a bell.

The chapter says a normally distributed random variable has a relative frequency histogram in the shape of a normal curve, also called a normal density curve. 

## Plain English

The normal distribution is the famous **bell curve**.

Most values are near the middle.
Fewer values are far away from the middle.

## Tiny example

Exam scores often look roughly normal:

* Many students score near the average.
* Few students score extremely low.
* Few students score extremely high.

## Exam clue

If the question says:

“normally distributed”
“normal curve”
“mean and standard deviation are…”
“find probability less than / greater than / between”

then you are probably using Chapter 6.

## Memory hint

Normal distribution = **bell-shaped curve**.

---

# 4. Shape of the Normal Curve

The normal curve looks like this idea:

Low values → middle values → high values

The highest point is in the middle.

The middle is the mean:

$$\mu$$

---

# 5. Mean ($\mu$) in Normal Distribution

## Definition

The mean ($\mu$) is the center of the normal curve.

The chapter says the mean ($\mu$) is the center of the curve. 

## Plain English

The mean tells us where the bell curve is centered.

## Tiny example

If exam scores are normally distributed with:

$$\mu=75$$

then the center of the curve is 75.

## Exam clue

The question may say:

“mean = 75”
“average = 75”
$$\mu=75$$

All mean the same thing.

## Memory hint

Mean = **middle of the bell**.

---

# 6. Standard Deviation ($\sigma$)

## Definition

The standard deviation ($\sigma$) tells how spread out the normal curve is.

## Plain English

It tells whether the values are close to the mean or far from the mean.

| Standard deviation | Meaning              |
| ------------------ | -------------------- |
| Small $\sigma$     | values close to mean |
| Large $\sigma$     | values spread out    |

## Tiny example

Class A:

$$\mu=75,\ \sigma=5$$

Most students are close to 75.

Class B:

$$\mu=75,\ \sigma=20$$

Scores are much more spread out.

## Exam clue

The question may say:

“standard deviation = 10”
$$\sigma=10$$

## Memory hint

Standard deviation = **spread amount**.

---

# 7. Properties of the Normal Distribution

The chapter lists these important properties of the normal density curve: it is symmetric about the mean, mean = median = mode, total area under the curve is 1, and the left and right areas around the mean are equal. 

Memorize these:

| Property                     | Simple meaning                             |
| ---------------------------- | ------------------------------------------ |
| Bell-shaped                  | looks like a bell                          |
| Symmetric                    | left side mirrors right side               |
| Mean = median = mode         | center, middle, and highest point are same |
| Total area = 1               | all probabilities together equal 1         |
| Left of mean = right of mean | each side is 0.5                           |
| One peak                     | normal distribution is unimodal            |

---

## Exam trick

If the question asks:

“Which does **not** apply to normal distribution?”

Then look for something false, like:

**bimodal**

Bimodal means two peaks.
Normal distribution has one peak.

---

# 8. Area Under the Curve

## Definition

In a normal distribution, probability is represented by **area under the curve**.

## Plain English

To find probability, we find area.

For example:

$$P(X<90)$$

means:

Area to the left of 90.

$$P(X>90)$$

means:

Area to the right of 90.

$$P(80<X<90)$$

means:

Area between 80 and 90.

## Exam clue

| Wording      | Area        |
| ------------ | ----------- |
| less than    | left side   |
| below        | left side   |
| greater than | right side  |
| exceeds      | right side  |
| more than    | right side  |
| between      | middle area |
| at most      | left side   |
| at least     | right side  |

## Memory hint

Probability = **area**.

---

# 9. Total Area Under the Curve

The total area under the normal curve is:

$$1$$

That means 100%.

Half is on the left of the mean:

$$0.5$$

Half is on the right of the mean:

$$0.5$$

---

# 10. Empirical Rule

The chapter says that for a normal distribution: about 68% of values lie within 1 standard deviation of the mean, 95% within 2 standard deviations, and 99.7% within 3 standard deviations. 

## Rule

| Interval                       | Approximate percentage |
| ------------------------------ | ---------------------: |
| $(\mu-\sigma)$ to $(\mu+\sigma)$   |                    68% |
| $(\mu-2\sigma)$ to $(\mu+2\sigma)$ |                    95% |
| $(\mu-3\sigma)$ to $(\mu+3\sigma)$ |                  99.7% |

---

## Plain English

Most values are close to the mean.

Very few values are far away.

---

## Tiny example

Suppose:

$$\mu=100$$

$$\sigma=10$$

Then:

### 68% range

$$100-10=90$$

$$100+10=110$$

So about 68% of values are between 90 and 110.

### 95% range

$$100-2(10)=80$$

$$100+2(10)=120$$

So about 95% of values are between 80 and 120.

### 99.7% range

$$100-3(10)=70$$

$$100+3(10)=130$$

So about 99.7% of values are between 70 and 130.

---

## Exam clue

If the question says:

“within one standard deviation”
“within two standard deviations”
“within three standard deviations”

use the empirical rule.

## Memory hint

Memorize:

$$68,\ 95,\ 99.7$$

---

# 11. Standard Normal Distribution

## Definition

The **standard normal distribution** is a normal distribution with:

$$\mu=0$$

$$\sigma=1$$

The chapter states that the standard normal random variable has mean 0 and standard deviation 1. 

## Plain English

It is the special normal curve used by the z-table.

## Why do we use it?

There are many normal distributions.

Example:

* mean 75, standard deviation 10
* mean 1050, standard deviation 222
* mean 2200, standard deviation 200

Instead of having a separate table for each curve, we convert everything to the standard normal curve using a z-score.

---

# 12. Z-Score

## Definition

A **z-score** tells how many standard deviations a value is from the mean.

Formula:

$$z=\frac{x-\mu}{\sigma}$$

The chapter gives this standardization formula for converting $X$ into $Z$. 

---

## Plain English

A z-score answers:

“How far is this value from the average?”

---

## What the sign means

|    Z-score | Meaning                 |
| ---------: | ----------------------- |
| positive z | value is above the mean |
| negative z | value is below the mean |
|      z = 0 | value equals the mean   |

---

## Tiny examples

### Example 1

$$z=1.5$$

This means the value is 1.5 standard deviations above the mean.

### Example 2

$$z=-0.68$$

This means the value is 0.68 standard deviations below the mean.

### Example 3

$$z=0$$

This means the value is exactly at the mean.

---

## Exam clue

If the question gives:

$$x,\ \mu,\ \sigma$$

and asks for z-score or probability, use:

$$z=\frac{x-\mu}{\sigma}$$

## Memory hint

Z-score = **distance from mean measured in standard deviations**.

---

# 13. How to Use the Z-Table

Most z-tables give:

$$P(Z<z)$$

This means the area to the **left** of the z-score.

---

## Main rules

### Rule 1: Less than

If the question asks:

$$P(X<a)$$

Convert $a$ to z, then use the table directly.

---

### Rule 2: Greater than

If the question asks:

$$P(X>a)$$

Convert $a$ to z, then do:

$$1-P(Z<z)$$

---

### Rule 3: Between

If the question asks:

$$P(a<X<b)$$

Convert both values to z-scores, then subtract:

$$P(Z<z_b)-P(Z<z_a)$$

---

# 14. Less Than Problems

## Example

Find:

$$P(X<900)$$

Suppose:

$$\mu=1050,\quad \sigma=222$$

---

## Step 1: Identify wording

“Less than” means left side.

---

## Step 2: Convert to z-score

$$z=\frac{x-\mu}{\sigma}$$

$$z=\frac{900-1050}{222}$$

$$z=\frac{-150}{222}$$

$$z=-0.68$$

---

## Step 3: Use z-table

$$P(Z<-0.68)=0.2483$$

---

## Final answer

$$0.2483$$

---

## Exam hint

“Less than” means use the left-table value directly.

---

# 15. Greater Than / Exceeds Problems

## Example

Find:

$$P(X>1500)$$

Suppose:

$$\mu=1050,\quad \sigma=222$$

---

## Step 1: Identify wording

“Exceeds” means greater than.

This is right side.

---

## Step 2: Convert to z-score

$$z=\frac{1500-1050}{222}$$

$$z=\frac{450}{222}$$

$$z=2.03$$

---

## Step 3: Use z-table

The z-table gives left side:

$$P(Z<2.03)=0.9788$$

---

## Step 4: Right side

$$P(Z>2.03)=1-0.9788$$

$$=0.0212$$

---

## Final answer

$$0.0212$$

---

## Exam hint

“Greater than” / “exceeds” means:

$$1-\text{left area}$$

---

# 16. Between Problems

## Example

Find:

$$P(1100<X<1225)$$

Suppose:

$$\mu=1050,\quad \sigma=222$$

---

## Step 1: Identify wording

“Between” means middle area.

---

## Step 2: Convert lower value to z-score

$$z_1=\frac{1100-1050}{222}$$

$$z_1=\frac{50}{222}$$

$$z_1=0.23$$

---

## Step 3: Convert upper value to z-score

$$z_2=\frac{1225-1050}{222}$$

$$z_2=\frac{175}{222}$$

$$z_2=0.79$$

---

## Step 4: Find left areas from z-table

$$P(Z<0.79)=0.7852$$

$$P(Z<0.23)=0.5909$$

---

## Step 5: Subtract

$$P(0.23<Z<0.79)=0.7852-0.5909$$

$$=0.1943$$

---

## Final answer

$$0.1943$$

Closest exam option may be:

$$0.1952$$

---

## Exam hint

“Between” means:

$$\text{larger left area} - \text{smaller left area}$$

---

# 17. Chapter 6 Final Exam Questions

Now we solve the Chapter 6 questions from your final/reference images.

---

# Question 16

**Which of the following properties does not apply to a theoretical normal distribution?**

Options:

A. The normal distribution is bell-shaped.
B. The mean, median, and mode are equal.
C. It is a bimodal distribution.
D. The area under the normal curve is equal to 1.

---

## Step 1: Identify the topic

This is asking about normal distribution properties.

---

## Step 2: Check option A

Normal distribution is bell-shaped.

This is true.

---

## Step 3: Check option B

For normal distribution:

$$\text{mean}=\text{median}=\text{mode}$$

This is true.

---

## Step 4: Check option C

Bimodal means two modes / two peaks.

Normal distribution has one peak.

So this is false.

---

## Step 5: Check option D

Total area under the normal curve is 1.

This is true.

---

## Final answer

**C. It is bimodal distribution**

---

## Exam clue

Normal distribution is **unimodal**, not bimodal.

---

## Common mistake

Thinking “symmetric” means two peaks. It does not. Symmetric means both sides are mirror images.

---

# Questions 17–19 Given Information

The problem says:

The production time is normally distributed with:

$$\mu=1050$$

$$\sigma=222$$

We use:

$$z=\frac{x-\mu}{\sigma}$$

---

# Question 17

**Find the probability that the production time is between 1100 and 1225 minutes.**

Options include:

A. 0.7823
B. 0.5871
C. 0.1952
D. None of these answers

---

## Step 1: Identify what is asked

The word **between** means:

$$P(1100<X<1225)$$

This is middle area.

---

## Step 2: Convert 1100 to z-score

Formula:

$$z=\frac{x-\mu}{\sigma}$$

Substitute:

$$z_1=\frac{1100-1050}{222}$$

$$z_1=\frac{50}{222}$$

$$z_1=0.225$$

Round:

$$z_1\approx0.23$$

---

## Step 3: Convert 1225 to z-score

$$z_2=\frac{1225-1050}{222}$$

$$z_2=\frac{175}{222}$$

$$z_2=0.788$$

Round:

$$z_2\approx0.79$$

---

## Step 4: Get z-table areas

$$P(Z<0.23)=0.5909$$

$$P(Z<0.79)=0.7852$$

---

## Step 5: Subtract

For between:

$$P(0.23<Z<0.79)=P(Z<0.79)-P(Z<0.23)$$

$$=0.7852-0.5909$$

$$=0.1943$$

---

## Final answer

Closest option:

**C. 0.1952**

Small differences happen because of rounding.

---

## Exam clue

Between two values = convert both to z, then subtract table values.

---

## Common mistake

Choosing 0.7852.

That is only the area to the left of 1225, not the area between 1100 and 1225.

---

# Question 18

**Find the probability that the production time exceeds 1500 minutes.**

Options include:

A. 0.9772
B. 0.0228
C. 1.9772
D. None of these answers

---

## Step 1: Identify wording

“Exceeds 1500” means:

$$P(X>1500)$$

This is right-tail probability.

---

## Step 2: Convert 1500 to z-score

$$z=\frac{1500-1050}{222}$$

$$z=\frac{450}{222}$$

$$z=2.027$$

Round:

$$z\approx2.03$$

---

## Step 3: Use z-table

$$P(Z<2.03)=0.9788$$

Depending on rounding/table, it may be close to:

$$0.9772$$

---

## Step 4: Since we need greater than, subtract from 1

$$P(Z>2.03)=1-0.9788$$

$$=0.0212$$

Closest option:

$$0.0228$$

---

## Final answer

**B. 0.0228**

---

## Exam clue

“Exceeds” = greater than = right side.

Right side means:

$$1-\text{table area}$$

---

## Common mistake

Choosing 0.9772.

That is the left side. The question asks for right side.

---

# Question 19

**Find the probability that assembly time is less than 900 minutes.**

Options include:

A. 0.20
B. 0.45
C. 0.50
D. None of these answers

---

## Step 1: Identify wording

“Less than 900” means:

$$P(X<900)$$

This is left-tail probability.

---

## Step 2: Convert 900 to z-score

$$z=\frac{900-1050}{222}$$

$$z=\frac{-150}{222}$$

$$z=-0.676$$

Round:

$$z\approx-0.68$$

---

## Step 3: Use z-table

$$P(Z<-0.68)=0.2483$$

---

## Final answer

$$0.2483$$

This is not 0.20, 0.45, or 0.50.

So the answer is:

**D. None of these answers**

---

## Exam clue

“Less than” = left side directly.

---

## Common mistake

Using:

$$1-0.2483$$

That would give the right side, but the question asks for less than.

---

# Question 20

**Scores are normally distributed with mean 75 and standard deviation 10. If a student scored 90, find the z-score.**

Options:

A. 1.5
B. 0.5
C. 1
D. None of these answers

---

## Step 1: Identify given values

$$x=90$$

$$\mu=75$$

$$\sigma=10$$

---

## Step 2: Formula

$$z=\frac{x-\mu}{\sigma}$$

---

## Step 3: Substitute

$$z=\frac{90-75}{10}$$

---

## Step 4: Calculate

$$z=\frac{15}{10}$$

$$z=1.5$$

---

## Final answer

**A. 1.5**

---

## Plain meaning

The student scored 1.5 standard deviations above the mean.

---

## Exam clue

If they only ask for z-score, you do not need a z-table.

Just use:

$$z=\frac{x-\mu}{\sigma}$$

---

## Common mistake

Doing:

$$\frac{75-90}{10}=-1.5$$

The formula is:

$$x-\mu$$

not:

$$\mu-x$$

---

# Chapter 6 Mini Cheat Sheet

| Topic                     | Formula / Rule                    |
| ------------------------- | --------------------------------- |
| Z-score                   | $z=\frac{x-\mu}{\sigma}$          |
| Standard normal mean      | $\mu=0$                           |
| Standard normal SD        | $\sigma=1$                        |
| Total area under curve    | 1                                 |
| Area left of mean         | 0.5                               |
| Area right of mean        | 0.5                               |
| Empirical rule            | 68%, 95%, 99.7%                   |
| Less than                 | use left area from z-table        |
| Greater than              | $1-\text{left area}$              |
| Between                   | upper left area − lower left area |
| Normal distribution shape | bell-shaped                       |
| Mean, median, mode        | equal                             |
| Normal distribution peak  | one peak, unimodal                |

---

# When You See This Wording, Use This Method

| Wording in exam                         | What to do               |
| --------------------------------------- | ------------------------ |
| “normally distributed”                  | use z-score              |
| “mean”                                  | $\mu$                    |
| “standard deviation”                    | $\sigma$                 |
| “find z-score”                          | $z=\frac{x-\mu}{\sigma}$ |
| “less than”                             | left area                |
| “below”                                 | left area                |
| “greater than”                          | right area               |
| “exceeds”                               | $1-\text{left area}$     |
| “between”                               | subtract two left areas  |
| “within 1 SD”                           | 68%                      |
| “within 2 SD”                           | 95%                      |
| “within 3 SD”                           | 99.7%                    |
| “does not apply to normal distribution” | look for false property  |

---

# Most Likely Chapter 6 Exam Question Types

1. Identify properties of normal distribution.
2. Choose which property is false.
3. Calculate z-score.
4. Find probability less than a value.
5. Find probability greater than / exceeds a value.
6. Find probability between two values.
7. Use the empirical rule.
8. Interpret whether a value is above or below average.
9. Recognize that total area under the curve is 1.
10. Understand that mean = median = mode in a normal distribution.

---

# Quick Practice With Answers

## Practice 1

A normal distribution has:

$$\mu=100,\quad \sigma=15$$

Find z-score for:

$$x=130$$

### Solution

$$z=\frac{130-100}{15}$$

$$z=\frac{30}{15}$$

$$z=2$$

Answer:

$$2$$

Meaning: 130 is 2 standard deviations above the mean.

---

## Practice 2

A normal distribution has:

$$\mu=50,\quad \sigma=5$$

Find z-score for:

$$x=40$$

### Solution

$$z=\frac{40-50}{5}$$

$$z=\frac{-10}{5}$$

$$z=-2$$

Answer:

$$-2$$

Meaning: 40 is 2 standard deviations below the mean.

---

## Practice 3

If:

$$P(Z<1.20)=0.8849$$

find:

$$P(Z>1.20)$$

### Solution

$$P(Z>1.20)=1-0.8849$$

$$=0.1151$$

Answer:

$$0.1151$$

---

## Practice 4

If:

$$P(Z<1.00)=0.8413$$

and:

$$P(Z<0.50)=0.6915$$

find:

$$P(0.50<Z<1.00)$$

### Solution

$$0.8413-0.6915=0.1498$$

Answer:

$$0.1498$$

---

## Practice 5

Which is false about normal distribution?

A. It is bell-shaped.
B. Mean = median = mode.
C. It has two peaks.
D. Total area equals 1.

Answer:

**C. It has two peaks.**

Normal distribution has one peak.

---

# Final Chapter 6 Memory Box

Memorize this:

$$z=\frac{x-\mu}{\sigma}$$

Then remember:

**Less than = left area**
**Greater than = 1 − left area**
**Between = subtract two left areas**

Also memorize normal properties:

**bell-shaped, symmetric, mean = median = mode, total area = 1, one peak.**
