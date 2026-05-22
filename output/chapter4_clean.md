## Chapter 4 — Probability and Counting Rules

Chapter 4 is about **chance**.

It teaches you how to answer questions like:

“What is the chance this happens?”
“How many possible outcomes are there?”
“Do I add, multiply, divide, or count arrangements?”

Your chapter covers sample spaces, probability types, addition rule, multiplication rule, conditional probability, and counting rules. The chapter outline says it focuses on **sample spaces and probability**, **rules of probability**, and **counting rules**. 

---

# 1. Basic Probability Words

## 1.1 Probability experiment

### Definition

A **probability experiment** is an action that gives **one result** by chance.

### Plain English

You do something, and you do not know exactly what will happen.

### Tiny examples

| Experiment  | Possible result        |
| ----------- | ---------------------- |
| Toss a coin | Head or Tail           |
| Roll a die  | 1, 2, 3, 4, 5, or 6    |
| Pick a card | Any card from the deck |

### Exam clue

When the question says:

“roll,” “toss,” “select,” “choose,” “pick randomly”

it is probably a probability experiment.

### Memory hint

Experiment = **the action**.

---

## 1.2 Outcome

### Definition

An **outcome** is one possible result of the experiment.

### Plain English

It is one answer that can happen.

### Tiny example

If you roll a die:

Outcomes are:

1, 2, 3, 4, 5, 6

### Exam clue

If they ask:

“What are the possible results?”

they mean outcomes.

### Memory hint

Outcome = **one result**.

---

## 1.3 Sample space

### Definition

The **sample space** is the list of **all possible outcomes**.

### Plain English

It is the full menu of everything that can happen.

### Tiny example

Toss two coins:

Sample space:

HH, HT, TH, TT

The chapter gives this same idea: tossing two coins gives HH, HT, TH, TT. 

### Exam clue

If the question says:

“write the sample space”
“all possible outcomes”
“possible results”

you list everything.

### Memory hint

Sample space = **the whole box**.

---

## 1.4 Event

### Definition

An **event** is a group of outcomes that we care about.

### Plain English

From the full menu, we choose the outcomes that match the question.

### Tiny example

Roll a die.

Sample space:

1, 2, 3, 4, 5, 6

Event A = getting an even number:

A = {2, 4, 6}

### Exam clue

If they say:

“probability of getting even”
“probability of at least one head”
“probability of selecting a male”

that is the event.

### Memory hint

Event = **what the question wants**.

---

## 1.5 Simple event vs compound event

| Type           | Meaning               | Example                         |
| -------------- | --------------------- | ------------------------------- |
| Simple event   | One outcome only      | rolling a 3                     |
| Compound event | More than one outcome | rolling an even number: 2, 4, 6 |

### Exam hint

If the event has only one result, it is simple.
If it has many results, it is compound.

---

# 2. Set Words in Probability

These appear a lot in probability questions.

## 2.1 Intersection: A ∩ B

### Definition

Intersection means outcomes that are in **A and B at the same time**.

### Plain English

It means **both**.

### Tiny example

A = {1, 2, 3, 4, 5}
B = {2, 4, 6, 8}

A ∩ B = {2, 4}

The chapter gives this same example. 

### Exam clue

Words like:

“and”
“both”
“male and in favor”

mean intersection.

### Memory hint

∩ looks like a bridge joining both groups.

---

## 2.2 Union: A ∪ B

### Definition

Union means outcomes in **A or B or both**.

### Plain English

It means **at least one of them happens**.

### Tiny example

A = {2, 3, 5, 8}
B = {3, 6, 8}

A ∪ B = {2, 3, 5, 6, 8}

The chapter gives this same idea. 

### Exam clue

Words like:

“or”
“A or B”
“male or in favor”

mean union.

### Memory hint

Union = **put groups together**.

---

## 2.3 Complement: Aᶜ

### Definition

The complement of A means **not A**.

### Plain English

Everything outside A.

### Tiny example

If A = red card, then Aᶜ = not red card = black card.

The chapter gives this red-card example. 

### Exam clue

Words like:

“not”
“did not”
“does not”
“at least one” sometimes uses complement

mean complement.

### Memory hint

Complement = **opposite**.

---

## 2.4 Mutually exclusive events

### Definition

Two events are **mutually exclusive** if they cannot happen at the same time.

### Plain English

If one happens, the other cannot happen.

### Tiny example

Roll one die.

A = even = {2, 4, 6}
B = odd = {1, 3, 5}

You cannot roll even and odd at the same time.

So they are mutually exclusive.

The chapter uses the same even/odd die example. 

### Exam clue

Look for:

“cannot happen together”
“one result only”
“even or odd on one roll”

### Memory hint

Mutually exclusive = **no overlap**.

---

# 3. What Probability Means

## Definition

Probability is a number from **0 to 1** that tells us how likely something is to happen.

The chapter says probability is between 0 and 1, where near 0 means unlikely, near 1 means almost certain, and 0.5 means equally likely and unlikely. 

| Probability | Meaning     |
| ----------- | ----------- |
| 0           | impossible  |
| close to 0  | unlikely    |
| 0.5         | half-half   |
| close to 1  | very likely |
| 1           | certain     |

### Example

Probability of rolling a 7 on one normal die = 0 because it is impossible.

Probability of rolling 1, 2, 3, 4, 5, or 6 = 1 because it must happen.

### Memory hint

Probability is like a battery:

0 = empty chance
1 = full chance

---

# 4. Three Types of Probability

The chapter divides probability into **classical**, **empirical**, and **subjective** probability. 

---

## 4.1 Classical probability

### Definition

Classical probability is used when all outcomes are **equally likely**.

### Formula


$$
P(A)=\frac{\text{number of ways A can happen}}{\text{total number of possible outcomes}}
$$


The chapter gives this formula for the classical method. 

### Plain English

Count the good outcomes.
Count all outcomes.
Divide.

### Tiny example

Roll a fair die.
Find probability of getting an even number.

Step 1: Even outcomes = 2, 4, 6
Step 2: Number of even outcomes = 3
Step 3: Total outcomes = 6


$$
P(even)=\frac{3}{6}=0.5
$$


### Exam clue

Use classical probability when the question says:

“fair coin”
“fair die”
“equally likely”
“randomly selected” from a clear group

### Memory hint

Classical = **count good ÷ count all**.

---

## 4.2 Empirical probability

### Definition

Empirical probability is based on **real data or experiment results**.

### Formula


$$
P(A)=\frac{\text{number of times A happened}}{\text{total number of trials}}
$$


The chapter uses the relative frequency method, such as 15 sevens in 100 dice rolls giving $15/100=0.15$. 

### Plain English

Look at what happened before.

### Tiny example

A basketball player made 30 shots out of 100.


$$
P(make)=\frac{30}{100}=0.30
$$


### Exam clue

Use empirical probability when the question says:

“survey”
“records show”
“in the past”
“out of 500 people”
“experiment was repeated”

### Memory hint

Empirical = **experience/data**.

---

## 4.3 Subjective probability

### Definition

Subjective probability is based on personal judgment or opinion.

### Plain English

It is an educated guess.

### Tiny example

A weather expert says:

“There is a 90% chance of rain tomorrow.”

The chapter gives this as an example of subjective probability. 

### Exam clue

Use subjective probability when the question says:

“expert believes”
“doctor thinks”
“based on judgment”
“estimated chance”

### Memory hint

Subjective = **someone’s opinion**.

---

# 5. Important Probability Rules

## 5.1 Complement rule

### Formula


$$
P(A^c)=1-P(A)
$$


or


$$
P(A)=1-P(A^c)
$$


### Plain English

If you know the chance something happens, you can find the chance it does not happen by subtracting from 1.

### Tiny example

If probability of passing = 0.80:


$$
P(failing)=1-0.80=0.20
$$


### Exam clue

Use complement when you see:

“not”
“did not”
“at least one”
“none”
“more than” sometimes

### Memory hint

Complement = **1 minus**.

---

## 5.2 Addition rule

Addition rule is used for **OR** questions.

### Special addition rule

Use this when events are mutually exclusive.


$$
P(A \cup B)=P(A)+P(B)
$$


The chapter gives this special addition rule for mutually exclusive events. 

### General addition rule

Use this when events can overlap.


$$
P(A \cup B)=P(A)+P(B)-P(A \cap B)
$$


### Why subtract overlap?

Because when you add A and B, the overlap gets counted twice.
So you subtract it once.

### Tiny example

In a class:

P(male) = 0.60
P(in favor) = 0.57
P(male and in favor) = 0.39

Find P(male or in favor):


$$
P(M \cup F)=0.60+0.57-0.39=0.78
$$


### Exam clue

Use addition rule when the question says:

“or”
“either”
“at least one of these”

### Memory hint

OR = ADD.

---

## 5.3 Multiplication rule

Multiplication rule is used for **AND** questions.

### Independent events

If events are independent:


$$
P(A \cap B)=P(A)\times P(B)
$$


### Plain English

Independent means one event does not affect the other.

### Tiny example

Toss a coin and roll a die.

P(head) = 1/2
P(rolling 6) = 1/6


$$
P(head \text{ and } 6)=\frac{1}{2}\times\frac{1}{6}=\frac{1}{12}
$$


### Exam clue

Use multiplication when you see:

“and”
“both”
“first and second”
“with replacement” usually means independent

### Memory hint

AND = MULTIPLY.

---

## 5.4 Conditional probability

### Definition

Conditional probability means probability of A **given that B already happened**.

### Formula


$$
P(A\mid B)=\frac{P(A \cap B)}{P(B)}
$$


### Plain English

You shrink the world.

You are no longer looking at everyone.
You only look inside the “given” group.

### Tiny example

From the teacher table:

Males = 60
Males in favor = 39

Find probability teacher is in favor **given that he is male**.

Step 1: “Given male” means only look at males.
Step 2: Total males = 60
Step 3: In favor among males = 39


$$
P(in\ favor\mid male)=\frac{39}{60}=0.65
$$


### Exam clue

Use conditional probability when the question says:

“given that”
“if we know that”
“among”
“from those who”

### Memory hint

Given = **new denominator**.

---

# 6. Counting Rules

Counting rules help when there are many possible outcomes and you do not want to list them one by one.

---

## 6.1 Fundamental counting rule

### Definition

If one task has $a$ choices and another task has $b$ choices, total choices are:


$$
a \times b
$$


### Plain English

Multiply the choices.

### Tiny example

A shirt has 3 colors.
Pants have 2 colors.

Total outfits:


$$
3 \times 2=6
$$


### Exam clue

Use this when there are stages:

first choice, second choice, third choice

### Memory hint

Stages = multiply.

---

## 6.2 Factorial

### Definition


$$
n! = n \times (n-1) \times (n-2) \times \dots \times 1
$$


### Tiny examples


$$
5! = 5 \times 4 \times 3 \times 2 \times 1 = 120
$$


$$
3! = 3 \times 2 \times 1 = 6
$$


### Exam clue

Factorial appears in arrangements, permutations, and combinations.

### Memory hint

Factorial means **count down and multiply**.

---

## 6.3 Permutation

### Definition

Permutation is an arrangement where **order matters**.

### Formula


$$
{}_nP_r=\frac{n!}{(n-r)!}
$$


### Plain English

Use permutation when ABC is different from BAC.

### Tiny example

How many ways can 3 students be arranged from 5 students?


$$
{}_5P_3=\frac{5!}{(5-3)!}
$$


$$
=\frac{5!}{2!}
$$


$$
=\frac{5 \times 4 \times 3 \times 2 \times 1}{2 \times 1}
$$


$$
=5 \times 4 \times 3=60
$$


### Exam clue

Use permutation when the question says:

“arrange”
“order”
“ranking”
“first, second, third”
“president, vice president, secretary”

### Memory hint

Permutation = **position matters**.

---

## 6.4 Combination

### Definition

Combination is selection where **order does not matter**.

### Formula


$$
{}_nC_r=\frac{n!}{r!(n-r)!}
$$


### Plain English

Use combination when choosing a group.

Ahmed, Ali, Omar is the same group as Omar, Ali, Ahmed.

### Tiny example

Choose 3 students from 5.


$$
{}_5C_3=\frac{5!}{3!(5-3)!}
$$


$$
=\frac{5!}{3!2!}
$$


$$
=\frac{5 \times 4}{2 \times 1}
$$


$$
=10
$$


### Exam clue

Use combination when the question says:

“choose”
“select”
“committee”
“group”
“team”

### Memory hint

Combination = **group only**.

---

# 7. Solving Chapter 4 Examples

## Example 1: Toss a coin twice. Probability of at least one head.

The chapter uses this example: sample space HH, HT, TH, TT, and event “at least one head” gives 3 outcomes out of 4. 

### Step 1: Identify what is asked

“At least one head” means one head or more.

### Step 2: Write sample space

HH, HT, TH, TT

### Step 3: Count good outcomes

Good outcomes:

HH, HT, TH

There are 3 good outcomes.

### Step 4: Count total outcomes

Total outcomes = 4

### Step 5: Use formula


$$
P(A)=\frac{good}{total}
$$


$$
P(at\ least\ one\ head)=\frac{3}{4}=0.75
$$


### Final answer


$$
0.75
$$


### Exam hint

“At least one” means **1 or more**.
Sometimes easier: $1-P(none)$.

---

## Example 2: Rolling a seven with two dice. 15 sevens in 100 rolls.

The chapter gives an empirical example where 15 sevens occurred in 100 rolls, so probability is $15/100=0.15$. 

### Step 1: Identify type

This is empirical probability because it uses actual experiment results.

### Step 2: Write formula


$$
P(A)=\frac{\text{number of times A happened}}{\text{total trials}}
$$


### Step 3: Substitute


$$
P(seven)=\frac{15}{100}
$$


### Step 4: Calculate


$$
P(seven)=0.15
$$


### Final answer


$$
0.15
$$


### Exam hint

If the question says “rolled 100 times and got 15,” use empirical probability.

---

## Example 3: Skydiving deaths

The chapter gives: 21 deaths out of 3,000,000 jumps. 

### Step 1: Identify type

This is empirical probability because it uses real data.

### Step 2: Formula


$$
P(death)=\frac{deaths}{jumps}
$$


### Step 3: Substitute


$$
P(death)=\frac{21}{3,000,000}
$$


### Step 4: Calculate


$$
P(death)=0.000007
$$


### Final answer


$$
0.000007
$$


### Exam hint

Deaths/survival are not equally likely, so do not use classical probability.

---

## Example 4: Activities table

The chapter gives this table:

| Number of activities | Frequency |
| -------------------- | --------: |
| 0                    |         8 |
| 1                    |        20 |
| 2                    |        12 |
| 3                    |         6 |
| 4                    |         3 |
| 5                    |         1 |

Total = 50 students.

The chapter converts these to relative frequencies and solves “at least one,” “three or more,” and “exactly two.” 

---

### A) Probability student participated in at least one activity

### Step 1: Identify wording

“At least one” means 1, 2, 3, 4, or 5.

### Step 2: Count good students


$$
20+12+6+3+1=42
$$


### Step 3: Total students


$$
50
$$


### Step 4: Divide


$$
P(at\ least\ one)=\frac{42}{50}=0.84
$$


### Final answer


$$
0.84
$$


### Faster method

“At least one” = not zero.


$$
P(at\ least\ one)=1-P(0)
$$


$$
=1-\frac{8}{50}
$$


$$
=1-0.16=0.84
$$


### Exam hint

“At least one” usually means use complement: $1-P(none)$.

---

### B) Probability student participated in three or more activities

### Step 1: Identify wording

“Three or more” means 3, 4, or 5.

### Step 2: Count good students


$$
6+3+1=10
$$


### Step 3: Divide by total


$$
P(3\ or\ more)=\frac{10}{50}=0.20
$$


### Final answer


$$
0.20
$$


### Exam hint

“Or more” means include the number itself and everything above it.

---

### C) Probability student participated in exactly two activities

### Step 1: Identify wording

“Exactly two” means only 2.

### Step 2: Frequency for 2 activities


$$
12
$$


### Step 3: Divide by total


$$
P(exactly\ 2)=\frac{12}{50}=0.24
$$


### Final answer


$$
0.24
$$


### Exam hint

“Exactly” means one value only.

---

## Example 5: Three-child family, two boys and one girl

The chapter compares empirical and classical probability using 500 families, where 180 had two boys and one girl. It also shows the classical sample space of 8 outcomes and 3 favorable outcomes. 

---

### A) Empirical method

### Step 1: Identify type

The question gives survey data, so use empirical probability.

### Step 2: Formula


$$
P(E)=\frac{\text{number with two boys and one girl}}{\text{total families}}
$$


### Step 3: Substitute


$$
P(E)=\frac{180}{500}
$$


### Step 4: Calculate


$$
P(E)=0.36
$$


### Final answer


$$
0.36 = 36\%
$$


### Exam hint

Survey data = empirical probability.

---

### B) Classical method

### Step 1: List sample space

For 3 children:

BBB, BBG, BGB, BGG, GBB, GBG, GGB, GGG

Total = 8

### Step 2: Find favorable outcomes

Two boys and one girl:

BBG, BGB, GBB

Favorable = 3

### Step 3: Formula


$$
P(E)=\frac{favorable}{total}
$$


### Step 4: Substitute


$$
P(E)=\frac{3}{8}
$$


### Step 5: Calculate


$$
P(E)=0.375
$$


### Final answer


$$
0.375 = 37.5\%
$$


### Exam hint

If boys/girls are equally likely and no survey data is needed, use classical probability.

---

# 8. Exam / Reference Questions Related to Chapter 4

## Question 1

Statement:

If A and B are two independent events such as $P(A)=0.5$, $P(B)=0.5$, then the probability of A and B happening is 0.1.

### Step 1: Identify topic

Independent events + “and” = multiplication rule.

### Step 2: Formula


$$
P(A \cap B)=P(A)\times P(B)
$$


### Step 3: Substitute


$$
P(A \cap B)=0.5 \times 0.5
$$


### Step 4: Calculate


$$
P(A \cap B)=0.25
$$


### Step 5: Compare with statement

The statement says 0.1, but the correct value is 0.25.

### Final answer

False.

### Exam hint

Independent + and = multiply.

### Common mistake

Students forget to multiply and guess from the options.

---

## Question 2

Statement:

If the experiment is repeated a large number of times, then the result of relative frequency probability tends to approach the result of classical probability.

### Step 1: Identify topic

This is the Law of Large Numbers.

The chapter says that as a procedure is repeated again and again, the relative frequency probability tends to approach the actual probability. 

### Step 2: Decide true or false

This statement matches the Law of Large Numbers.

### Final answer

True.

### Exam hint

“Repeated large number of times” = Law of Large Numbers.

### Common mistake

Thinking empirical probability is always exactly equal to classical probability. It is not always exactly equal, but it gets closer with many trials.

---

## Question 3

Statement:

A die is rolled, the probability that the number less than 5 is obtained is 0.3.

### Step 1: Identify topic

Classical probability because a die has equally likely outcomes.

### Step 2: List outcomes less than 5

1, 2, 3, 4

Good outcomes = 4

### Step 3: Total outcomes

A die has 6 outcomes.

### Step 4: Formula


$$
P(less\ than\ 5)=\frac{4}{6}
$$


### Step 5: Calculate


$$
\frac{4}{6}=0.6667
$$


### Step 6: Compare

The statement says 0.3, but correct is about 0.67.

### Final answer

False.

### Exam hint

“Less than 5” does not include 5.

### Common mistake

Counting only 1, 2, 3 and forgetting 4.

---

## Question 4

Statement:

The Cricket team had 16 games. Each game result had 3 possible outcomes: tie, win, loss. Total possible outcomes are 48.

### Step 1: Identify topic

Counting rule.

### Step 2: Understand the situation

Each game has 3 choices.

There are 16 games.

### Step 3: Use multiplication rule


$$
3^{16}
$$


### Step 4: Calculate


$$
3^{16}=43,046,721
$$


### Step 5: Compare

48 would be $16 \times 3$, but that is wrong here.

### Final answer

False.

### Exam hint

When each stage has choices, multiply repeatedly.
For 16 games with 3 choices each, use $3^{16}$, not $16 \times 3$.

### Common mistake

Multiplying number of games by outcomes instead of using powers.

---

# Teacher Table Questions

Table:

| Group   | In favor | Against | Total |
| ------- | -------: | ------: | ----: |
| Males   |       39 |      21 |    60 |
| Females |       18 |      22 |    40 |
| Total   |       57 |      43 |   100 |

---

## Question 5

The probability to select a male teacher is:

Options include 0.60.

### Step 1: Identify what is asked

Probability of male.

### Step 2: Find total males

Males = 60

### Step 3: Find total people

Total = 100

### Step 4: Divide


$$
P(male)=\frac{60}{100}=0.60
$$


### Final answer

A) 0.60

### Exam hint

When it asks one category only, use:


$$
\frac{category\ total}{grand\ total}
$$


### Common mistake

Using 39 instead of 60.
39 is males in favor, not all males.

---

## Question 6

The probability to randomly select a male teacher who is in favor is:

Options include 0.39.

### Step 1: Identify wording

“Male teacher who is in favor” means male AND in favor.

### Step 2: Find the intersection

Male and in favor = 39

### Step 3: Grand total

Total = 100

### Step 4: Divide


$$
P(male\ and\ in\ favor)=\frac{39}{100}=0.39
$$


### Final answer

B) 0.39

### Exam hint

“And” means intersection.

### Common mistake

Dividing by 60.
You divide by 60 only if it says “given male.”

---

## Question 7

The probability to select a female who is against is:

Options include 0.22.

### Step 1: Identify wording

Female AND against.

### Step 2: Find the intersection

Female and against = 22

### Step 3: Grand total

Total = 100

### Step 4: Divide


$$
P(female\ and\ against)=\frac{22}{100}=0.22
$$


### Final answer

B) 0.22

### Exam hint

No word “given,” so denominator is the grand total.

### Common mistake

Using 22/40.
That would mean “against given female.”

---

## Question 8

The probability to select a teacher who is in favor given that he is male:

Options include 0.65.

### Step 1: Identify wording

“Given that he is male” means conditional probability.

### Step 2: New denominator

Only males.

Total males = 60

### Step 3: Good outcomes inside males

Males in favor = 39

### Step 4: Divide


$$
P(in\ favor\mid male)=\frac{39}{60}
$$


### Step 5: Calculate


$$
\frac{39}{60}=0.65
$$


### Final answer

B) 0.65

### Exam hint

“Given” = denominator becomes the given group.

### Common mistake

Using 39/100.
That is “male and in favor,” not “in favor given male.”

---

## Question 9

Employees surveyed: 600 total employees.
400 had good experience.
Find probability that an employee **did not have good experience**.

### Step 1: Identify wording

“Did not have good experience” means complement.

### Step 2: Find not good experience


$$
600-400=200
$$


### Step 3: Divide by total


$$
P(not\ good)=\frac{200}{600}
$$


### Step 4: Calculate


$$
P(not\ good)=0.3333
$$


### Final answer

B) 0.33

### Exam hint

“Did not” = complement.

### Common mistake

Using 400/600, which gives probability of good experience, not bad/no good experience.

---

## Question 10

Three members from the jury will be selected out of 5 to judge a case. How many ways is the arrangement possible?

Options shown: 10, 15, 20, 25.

### Important note

The word “arrangement” usually means order matters, so mathematically:


$$
{}_5P_3=60
$$


But 60 is not in the options. Since the options include 10, the exam probably means **selection**, not arrangement.

### Step 1: Identify likely topic

Selecting 3 from 5.

Order does not matter because they are just members of a jury.

### Step 2: Use combination


$$
{}_5C_3=\frac{5!}{3!(5-3)!}
$$


### Step 3: Substitute


$$
{}_5C_3=\frac{5!}{3!2!}
$$


### Step 4: Simplify


$$
=\frac{5 \times 4}{2 \times 1}
$$


$$
=10
$$


### Final answer

A) 10

### Exam hint

“Selected out of” usually means combination.

### Common mistake

Using permutation when the exam actually wants selection.

---

# Chapter 4 Mini Cheat Sheet

| Topic                     | Formula                                      |                             |
| ------------------------- | -------------------------------------------- | --------------------------- |
| Classical probability     | $P(A)=\frac{good}{total}$                    |                             |
| Empirical probability     | $P(A)=\frac{times A happened}{total trials}$ |                             |
| Complement                | $P(A^c)=1-P(A)$                              |                             |
| Mutually exclusive OR     | $P(A\cup B)=P(A)+P(B)$                       |                             |
| General OR                | $P(A\cup B)=P(A)+P(B)-P(A\cap B)$            |                             |
| Independent AND           | $P(A\cap B)=P(A)P(B)$                        |                             |
| Conditional probability   | $P(A                                         \mid  B)=\frac{P(A\cap B)}{P(B)}$ |
| Fundamental counting rule | multiply choices                             |                             |
| Permutation               | ${}_nP_r=\frac{n!}{(n-r)!}$                    |                             |
| Combination               | ${}_nC_r=\frac{n!}{r!(n-r)!}$                  |                             |

---

# When You See This Wording, Use This Method

| Wording in question                       | What to use             |
| ----------------------------------------- | ----------------------- |
| “fair die,” “fair coin,” “equally likely” | Classical probability   |
| “survey,” “records,” “out of 500”         | Empirical probability   |
| “expert believes,” “estimated”            | Subjective probability  |
| “not,” “did not,” “none”                  | Complement rule         |
| “or”                                      | Addition rule           |
| “and,” “both”                             | Multiplication rule     |
| “given that”                              | Conditional probability |
| “at least one”                            | Usually complement      |
| “exactly”                                 | One value only          |
| “less than 5”                             | Do not include 5        |
| “at most 5”                               | Include 5               |
| “at least 5”                              | Include 5               |
| “arrange/order/rank”                      | Permutation             |
| “choose/select/group/committee”           | Combination             |

---

# Most Likely Chapter 4 Exam Question Types

1. True/False about probability rules.
2. Finding probability from a table.
3. Conditional probability using “given.”
4. Complement questions using “not.”
5. Counting sample spaces.
6. Choosing between permutation and combination.
7. Classical vs empirical probability.
8. Interpreting “and” vs “or.”

---

# Quick Practice With Answers

## Practice 1

A die is rolled. Find probability of getting a number greater than 4.

Numbers greater than 4: 5, 6


$$
P=\frac{2}{6}=0.333
$$


Answer: 0.333

---

## Practice 2

A coin is tossed 3 times. How many total outcomes?

Each toss has 2 outcomes.


$$
2^3=8
$$


Answer: 8

---

## Practice 3

Out of 200 students, 50 are absent. Find probability a student is absent.


$$
P=\frac{50}{200}=0.25
$$


Answer: 0.25

---

## Practice 4

Out of 200 students, 50 are absent. Find probability a student is not absent.


$$
P=1-0.25=0.75
$$


Answer: 0.75

---

## Practice 5

Choose 2 students from 6. How many groups?


$$
{}_6C_2=\frac{6!}{2!4!}
$$


$$
=\frac{6 \times 5}{2}=15
$$


Answer: 15

---

## Practice 6

Arrange 2 students from 6 as first and second place.


$$
{}_6P_2=\frac{6!}{4!}
$$


$$
=6 \times 5=30
$$


Answer: 30
